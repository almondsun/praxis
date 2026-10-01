import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .core import ROOT, PraxisError, read_json, run, write_json

INFRASTRUCTURE = ('cannot establish app-server socket mount isolation',
                  'error building bubblewrap command', 'read-only file system',
                  "you've hit your usage limit", 'rate limit reached', 'insufficient_quota',
                  'authentication failed', '401 unauthorized', 'missing bearer', 'model is not available')


def infrastructure_errors(log):
    errors = []
    for line in Path(log).read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        # Inspect tool/error events, not source-code snippets in a model response.
        item = row.get('item', {})
        if row.get('type') == 'turn.failed':
            errors.append(row)
            continue
        if item.get('type') == 'command_execution':
            if item.get('status') != 'failed' and item.get('exit_code') in (None, 0):
                continue
            value = str(item.get('aggregated_output', ''))
        elif row.get('type') == 'error' or item.get('type') == 'error':
            value = str(row.get('message', item.get('message', '')))
        else:
            continue
        value = value.lower().replace('’', "'")
        if any(marker in value for marker in INFRASTRUCTURE):
            errors.append(row)
    return errors


def execute(layout, project, prompt, label, evidence, *, readonly=False, schema=None, interrupt_when=None,
            trusted_fixture=False, timeout=None):
    """One invocation. Never automatically retries or waits for account resets."""
    evidence = Path(evidence); evidence.mkdir(parents=True, exist_ok=True)
    route = read_json(ROOT / 'config/routing.json')['quality']
    command = [str(layout.executable('codex')), 'exec', '--strict-config', '--json',
               '-m', route['model'], '-c', f'model_reasoning_effort="{route["effort"]}"',
               '-c', 'approval_policy="never"', '-s', 'read-only' if readonly else 'workspace-write',
               '-C', str(project), '-o', str(evidence / (label + '-final.txt'))]
    if not readonly:
        git_dir = run(['git', 'rev-parse', '--absolute-git-dir'], cwd=project, env=layout.env()).strip()
        common_dir = run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=project, env=layout.env()).strip()
        command += ['-c', 'sandbox_workspace_write.writable_roots=' + json.dumps(sorted({git_dir, common_dir}))]
    else:
        command += ['-c', 'mcp_servers.engram.enabled=false']
    from .install import doctor
    check = doctor(layout)
    if check['errors']:
        raise PraxisError('Configuration changed; refusing hook-trust bypass: ' + str(check['errors']))
    if trusted_fixture:
        if not (Path(project).resolve().is_relative_to(Path(evidence).resolve())):
            raise PraxisError('Hook trust bypass is restricted to disposable self-test fixtures')
        command.insert(2, '--dangerously-bypass-hook-trust')
    if schema:
        command += ['--output-schema', str(schema)]
    command += [prompt]
    log = evidence / (label + '.jsonl')
    start = time.monotonic(); interrupted = False; timed_out = False
    with log.open('w') as stdout, (evidence / (label + '-stderr.log')).open('w') as stderr:
        proc = subprocess.Popen(command, env=layout.fixture_env() if trusted_fixture else layout.env(), stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while proc.poll() is None:
                if interrupt_when and interrupt_when():
                    interrupted = True
                    os.killpg(proc.pid, signal.SIGTERM)
                    break
                if timeout is not None and time.monotonic() - start > timeout:
                    timed_out = True
                    os.killpg(proc.pid, signal.SIGTERM)
                    break
                time.sleep(1)
            try:
                code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); code = proc.wait()
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            raise
    errors = infrastructure_errors(log)
    result = {'exit_code': code, 'seconds': round(time.monotonic() - start, 2),
              'controlled_interruption': interrupted, 'infrastructure_errors': errors,
              'timed_out': timed_out, 'deadline_seconds': timeout,
              'stop_reason': 'planned_checkpoint' if interrupted else 'phase_deadline' if timed_out else
                             'runtime_failure' if code or errors else 'completed',
              'log': str(log), 'manual_resume_required': bool(code or errors or timed_out)}
    write_json(evidence / (label + '-result.json'), result)
    if (code and not interrupted) or errors or timed_out:
        raise PraxisError(f'{label} stopped; see {evidence}. Resume only when you choose.')
    return result


def resume(layout, project):
    project = Path(project).expanduser().resolve()
    run(['git', 'rev-parse', '--show-toplevel'], cwd=project, env=layout.env())
    checkpoint = project / 'PRAXIS_CHECKPOINT.md'
    if not checkpoint.is_file():
        raise PraxisError('No PRAXIS_CHECKPOINT.md. Inspect this repository interactively; do not assume a clean start.')
    evidence = layout.state / 'runs' / str(time.time_ns())
    result = execute(layout, project,
        'The user explicitly resumes this task now. Start with Git status/log and PRAXIS_CHECKPOINT.md; '
        'read the approved plan and Superpowers ledger. Reconcile uncommitted changes, then resume only '
        'unfinished authorized work. Prior chat is unavailable. Engram is advisory. Follow Praxis quality '
        'gates; report blockers without inventing success. No push or external mutation is authorized.',
        'manual-resume', evidence)
    return {'invocation_finished': True, 'quality_claim': 'Inspect verification and review evidence; CLI exit alone is not completion.', **result}
