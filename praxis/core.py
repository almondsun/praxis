from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class PraxisError(RuntimeError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic(path, content, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    atomic(path, json.dumps(value, indent=2) + '\n')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(args, *, env=None, cwd=None, capture=True, timeout=120, include_stderr=False):
    result = subprocess.run([str(a) for a in args], env=env, cwd=cwd,
                            text=True, capture_output=capture, timeout=timeout)
    if result.returncode:
        raise PraxisError(f'{args[0]} exited {result.returncode}: '
                          + ((result.stderr or '')[-2000:] if capture else 'see terminal'))
    return (result.stdout or '') + ((result.stderr or '') if include_stderr else '')


def fetch_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'praxis-bootstrap'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


class Layout:
    def __init__(self, home=None):
        self.home = Path(home or Path.home()).expanduser().resolve()
        self.data = self.home / '.local/share/praxis'
        self.state = self.home / '.local/state/praxis'
        self.codex = self.home / '.codex'
        self.bin = self.home / '.local/bin'
        self.lock = read_json(ROOT / 'versions.lock.json')

    def component(self, name):
        return self.data / 'components' / (name + '-' + self.lock['components'][name]['version'])

    def executable(self, name):
        entry = self.lock['components'][name]
        return self.component(name) / entry['executable']

    def project_options(self):
        return {'engram': str(self.executable('engram')),
                'protected_roots': [str(ROOT), str(ROOT.parent / 'agentcore'), str(self.codex),
                                    str(self.data), str(self.home / '.config'), str(self.home / '.agents')]}

    def env(self):
        env = dict(os.environ)
        for key in list(env):
            if key.startswith(('CODEX_', 'GENTLE_', 'ENGRAM_', 'XDG_', 'GIT_')):
                env.pop(key)
        env.update(HOME=str(self.home), CODEX_HOME=str(self.codex),
                   XDG_CONFIG_HOME=str(self.home / '.config'),
                   XDG_DATA_HOME=str(self.home / '.local/share'),
                   XDG_STATE_HOME=str(self.home / '.local/state'),
                   XDG_CACHE_HOME=str(self.home / '.cache'),
                   GENTLE_AI_CHANNEL='stable',
                   GENTLE_AI_ENGRAM_SETUP_MODE='off',
                   PYTHONDONTWRITEBYTECODE='1',
                   PATH=os.pathsep.join([str(self.bin), '/usr/local/bin', '/usr/bin', '/bin']))
        return env

    def fixture_env(self):
        env = self.env()
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                   GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='core.hooksPath',
                   GIT_CONFIG_VALUE_0='/dev/null', GIT_CONFIG_KEY_1='commit.gpgsign',
                   GIT_CONFIG_VALUE_1='false')
        return env


def tree_hashes(root):
    root = Path(root)
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and not p.is_symlink()}
