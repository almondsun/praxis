"""Read-only app-server inspection. No model turn, quota polling or retry loop."""
import json
import os
import selectors
import subprocess
import time

from .core import ROOT, PraxisError, read_json


def inspect_runtime(layout):
    process = subprocess.Popen([str(layout.executable('codex')), 'app-server', '--stdio'],
                               env=layout.env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0)
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    buffer = bytearray()

    def send(value):
        process.stdin.write((json.dumps(value) + '\n').encode()); process.stdin.flush()

    def response(ident):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if b'\n' not in buffer:
                if not selector.select(timeout=1):
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    raise PraxisError('Codex app-server closed its inspection stream')
                buffer.extend(data)
                continue
            line, _, rest = buffer.partition(b'\n'); buffer[:] = rest
            row = json.loads(line)
            if row.get('id') == ident:
                if 'error' in row:
                    raise PraxisError('Codex runtime inspection failed: ' + json.dumps(row['error']))
                return row['result']
        raise PraxisError('Codex runtime inspection timed out')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'praxis', 'version': '1'}}})
        response(1); send({'method': 'initialized', 'params': {}})
        models = []; cursor = None; ident = 2
        while True:
            params = {'includeHidden': True}
            if cursor:
                params['cursor'] = cursor
            send({'id': ident, 'method': 'model/list', 'params': params})
            page = response(ident); ident += 1
            models.extend(page.get('data', [])); cursor = page.get('nextCursor')
            if not cursor:
                break
        routing = read_json(ROOT / 'config/routing.json')
        missing = []
        for tier, rule in routing.items():
            match = next((m for m in models if m.get('model', m.get('id')) == rule['model']), None)
            if not match or rule['effort'] not in {r['reasoningEffort'] for r in match.get('supportedReasoningEfforts', [])}:
                missing.append(tier)
        send({'id': ident, 'method': 'account/rateLimits/read', 'params': {}})
        quota = response(ident)
        result = {'routing_available': not missing, 'missing_tiers': missing,
                  'ordinary_usage_allowed': quota.get('ordinaryUsageAllowed'),
                  'quota': {k: quota[k] for k in ('rateLimits', 'rateLimitsByLimitId') if k in quota}}
        return result
    finally:
        selector.close()
        if process.stdin:
            process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
