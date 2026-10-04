"""Safe Git-root ownership and upstream Engram initialization, without commits."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess


class ProjectError(RuntimeError):
    pass


def project_env(env=None):
    result = dict(os.environ if env is None else env)
    if result.get('ENGRAM_PROJECT'):
        raise ProjectError('ENGRAM_PROJECT conflicts with root-owned project discovery; inspect it explicitly.')
    for key in list(result):
        if key.startswith(('GIT_', 'ENGRAM_')):
            result.pop(key)
    return result


def git(directory, *args, env=None, check=True):
    executable = shutil.which('git', path='/usr/bin:/bin')
    if not executable:
        raise ProjectError('System Git is unavailable.')
    result = subprocess.run([executable, '-C', str(directory), *args], env=env,
                            capture_output=True, text=True, timeout=30)
    if check and result.returncode:
        raise ProjectError('Git operation failed; inspect repository ownership/permissions before retrying.')
    return result


def nearest_git_root(directory, env):
    existing = directory
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    if not existing.is_dir():
        raise ProjectError('Project entry must be a directory.')
    result = git(existing, 'rev-parse', '--show-toplevel', env=env, check=False)
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    if 'not a git repository' not in result.stderr.lower():
        raise ProjectError('Git root detection failed; refusing to initialize over an uncertain repository.')
    return None


def protect(root, protected_roots, greenfield):
    homes = {Path.home().resolve(), Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()}
    exact = {Path(p) for p in ('/', '/home', '/opt', '/tmp')} | homes
    system = [Path(p) for p in ('/etc', '/usr', '/var', '/proc', '/sys', '/dev', '/run',
                               '/boot', '/bin', '/sbin', '/lib', '/lib64')]
    reserved = [Path(p).resolve() for p in protected_roots]
    if root in exact or any(root == p or root.is_relative_to(p) for p in system + reserved):
        raise ProjectError('Protected infrastructure/sensitive root; automatic project initialization is forbidden.')
    if greenfield and any(part in ('.codex', '.agents', '.config', '.local') for part in root.parts):
        raise ProjectError('Greenfield Git creation inside infrastructure state is forbidden; select a project root.')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def read_binding(path):
    if path.is_symlink() or not path.is_file():
        raise ProjectError('Existing Engram binding must be a regular file: ' + str(path))
    try:
        result = json.loads(path.read_text(), object_pairs_hook=unique_object)
        if not isinstance(result, dict):
            raise ValueError('Object required')
        return result
    except (OSError, UnicodeError, ValueError):
        raise ProjectError('Malformed/unreadable Engram binding; no repair or overwrite: ' + str(path)) from None


def canonical(name):
    if not isinstance(name, str) or not name.strip() or any(c in name for c in '/\\') \
            or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ProjectError('Invalid Engram project name; no automatic repair.')
    result = name.strip().lower()
    while '--' in result or '__' in result:
        result = result.replace('--', '-').replace('__', '_')
    return result


def current_identity(engram, root, env):
    messages = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'praxis-project-entry', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
         'params': {'name': 'mem_current_project', 'arguments': {}}}]
    process = subprocess.run([str(engram), 'mcp', '--tools=agent'], cwd=root, env=env,
                             input=''.join(json.dumps(m) + '\n' for m in messages),
                             capture_output=True, text=True, timeout=30)
    if process.returncode:
        raise ProjectError('Pinned Engram identity verification failed; no memory success is claimed.')
    try:
        reply = next(json.loads(line) for line in process.stdout.splitlines()
                     if json.loads(line).get('id') == 2)
        if 'error' in reply or reply['result'].get('isError'):
            raise ValueError('MCP error')
        identity = json.loads(next(c['text'] for c in reply['result']['content'] if c['type'] == 'text'))
        if not identity.get('project') or identity.get('error_hint'):
            raise ValueError('Unresolved identity')
        return identity
    except (ValueError, KeyError, TypeError, StopIteration):
        raise ProjectError('Pinned Engram did not return an unambiguous project identity.') from None


def prepare_project(directory, *, engram, protected_roots=(), greenfield=False, env=None):
    requested = Path(directory).expanduser().absolute()
    directory = requested.resolve()
    env = project_env(env)
    root = nearest_git_root(directory, env)
    created_git = False
    if root is None:
        protect(directory, protected_roots, greenfield)
        if not greenfield:
            raise ProjectError('No Git repository. Confirm the intended greenfield root with Praxis start --greenfield; no files changed.')
        if requested.is_symlink() or (directory.exists() and any(directory.iterdir())):
            raise ProjectError('Explicit greenfield creation requires a pristine real directory; no Git initialization performed.')
        directory.mkdir(parents=True, exist_ok=True)
        if nearest_git_root(directory, env) is not None:
            raise ProjectError('Git ownership changed during greenfield setup; stop and inspect, no nested Git initialization.')
        git(directory, '-c', 'init.templateDir=', 'init', '-q', env=env)
        root = nearest_git_root(directory, env)
        if root != directory:
            raise ProjectError('New Git root did not resolve to the explicitly selected project directory.')
        created_git = True
    if not directory.is_dir():
        raise ProjectError('Project entry directory does not exist; enclosing Git repository was not changed.')
    protect(root, protected_roots, False)
    # Root ownership wins; do not overwrite an existing subproject identity.
    for parent in (directory, *directory.parents):
        if parent == root:
            break
        config = parent / '.engram/config.json'
        if config.exists() or config.is_symlink():
            raise ProjectError('Subproject Engram binding conflicts with root-owned entry; inspect scope explicitly.')
    engdir = root / '.engram'
    if engdir.is_symlink() or (engdir.exists() and not engdir.is_dir()):
        raise ProjectError('Existing .engram must be a real directory; no replacement.')
    config = engdir / 'config.json'
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir', env=env).stdout.strip())
    private = common / 'engram-project-identity.json'
    private_name = None
    if private.exists() or private.is_symlink():
        binding = read_binding(private)
        private_name = canonical(binding.get('project'))
        token = binding.get('id')
        if binding.get('version') != 1 or not isinstance(token, str) or len(token) != 32 \
                or any(c not in '0123456789abcdefABCDEF' for c in token) or private_name != binding['project']:
            raise ProjectError('Malformed private Engram Git identity; no repair or override.')
    initialized = False
    if config.exists() or config.is_symlink():
        name = canonical(read_binding(config).get('project_name'))
        if private_name is not None and private_name != name:
            raise ProjectError('Conflicting Engram root/private identities; no automatic replacement.')
    elif private_name is not None:
        name = private_name
    else:
        process = subprocess.run([str(engram), 'init'], cwd=root, env=env,
                                 capture_output=True, text=True, timeout=30)
        if process.returncode:
            raise ProjectError('Pinned Engram initialization failed; inspect preserved state, do not force-overwrite.')
        name = canonical(read_binding(config).get('project_name'))
        initialized = True
    identity = current_identity(engram, root, env)
    allowed_paths = {root}
    if private_name is not None and common.name == '.git':
        allowed_paths.add(common.parent.resolve())  # Upstream linked-worktree identity.
    path = identity.get('project_path')
    if identity['project'] != name or not isinstance(path, str) or not Path(path).is_absolute() \
            or Path(path).resolve() not in allowed_paths:
        raise ProjectError('Engram canonical identity does not match the resolved Git project; stop and inspect.')
    return {'root': str(root), 'project': name, 'git_created': created_git,
            'engram_initialized': initialized, 'identity': identity}
