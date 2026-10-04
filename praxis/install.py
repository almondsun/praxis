"""Pinned artifact installation and narrowly owned Codex configuration."""
import json
import hashlib
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import sys
import tarfile
import tempfile
import tomllib
import urllib.request

from .core import ROOT, PraxisError, atomic, read_json, run, sha, tree_hashes, write_json
from .launchers import installed_errors, require_cutover_resolution


def unpack(archive, destination, strip_root=False):
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        # Release archives are data: never allow traversal, devices or link escapes.
        for member in members:
            parts = Path(member.name).parts
            if Path(member.name).is_absolute() or '..' in parts or not (member.isfile() or member.isdir()):
                raise PraxisError('Unsafe archive entry: ' + member.name)
            if strip_root:
                member.name = str(Path(*parts[1:])) if len(parts) > 1 else '.'
        tar.extractall(destination, members=members, filter='data')


def verify_component(layout, name):
    entry = layout.lock['components'][name]
    dest = layout.component(name)
    receipt = dest / '.praxis-receipt.json'
    if receipt.exists():
        saved = read_json(receipt)
        if saved['artifact_sha256'] != entry['sha256']:
            raise PraxisError('Installed version has different locked artifact: ' + name)
        actual = tree_hashes(dest); actual.pop('.praxis-receipt.json', None)
        if saved['files'] != actual:
            raise PraxisError('Installed component modified: ' + name)
        return True
    return False


def install_component(layout, name):
    entry = layout.lock['components'][name]
    dest = layout.component(name)
    if verify_component(layout, name):
        return
    if dest.exists():
        raise PraxisError('Incomplete installation; inspect and remove only this component: ' + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as temporary:
        temporary = Path(temporary)
        archive = temporary / 'release.tar.gz'
        request = urllib.request.Request(entry['url'], headers={'User-Agent': 'praxis-bootstrap'})
        with urllib.request.urlopen(request, timeout=120) as response, archive.open('wb') as handle:
            shutil.copyfileobj(response, handle)
        if sha(archive) != entry['sha256']:
            raise PraxisError('Release checksum mismatch: ' + name)
        tree = temporary / 'tree'; tree.mkdir()
        unpack(archive, tree, entry.get('strip_root', False))
        write_json(tree / '.praxis-receipt.json', {'artifact_sha256': entry['sha256'], 'files': tree_hashes(tree)})
        tree.rename(dest)


def link(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() and path.resolve() == target.resolve():
        return
    if path.is_symlink() and '/praxis/components/' in str(path.readlink()):
        path.unlink()
    if path.exists() or path.is_symlink():
        raise PraxisError('Refusing to overwrite existing launcher: ' + str(path))
    path.symlink_to(target)


def check_ownership(layout):
    marker = layout.codex / 'praxis-install.json'
    if marker.exists():
        manifest = read_json(marker)
        for relative, digest in manifest.get('files', {}).items():
            path = layout.codex / relative
            if not managed_file_matches(path, relative, digest, manifest):
                raise PraxisError('Managed file changed; inspect before replacing: ' + relative)
        return
    activation = ('config.toml', 'AGENTS.md', 'AGENTS.override.md', 'hooks.json',
                  'agents', 'rules', 'skills', 'plugins')
    conflicts = [name for name in activation if (layout.codex / name).exists()]
    skills = layout.home / '.agents/skills'
    if skills.exists() and any(skills.iterdir()):
        conflicts.append(str(skills))
    if conflicts:
        raise PraxisError('Existing customization requires explicit cutover: ' + ', '.join(conflicts))


def native_consent(config):
    """Separate native consent records; never normalize hook enable/disable edits."""
    projects = config.pop('projects', {})
    if not isinstance(projects, dict) or any(
            not isinstance(value, dict) or set(value) != {'trust_level'} or
            value['trust_level'] not in ('trusted', 'untrusted') for value in projects.values()):
        raise PraxisError('Unexpected project configuration; inspect before continuing')
    hooks = config.get('hooks', {})
    if not isinstance(hooks, dict):
        raise PraxisError('Unexpected hook configuration; inspect before continuing')
    states = hooks.pop('state', {})
    if not isinstance(states, dict) or any(
            not isinstance(key, str) or not key or not isinstance(value, dict) or
            set(value) != {'trusted_hash'} or not isinstance(value['trusted_hash'], str) or
            not re.fullmatch(r'sha256:[a-f0-9]{64}', value['trusted_hash'])
            for key, value in states.items()):
        raise PraxisError('Unexpected hook consent configuration; inspect before continuing')
    if not hooks:
        config.pop('hooks', None)
    return projects, states


def configuration_digest(path):
    """Codex stores native project/hook consent; all execution settings stay bound."""
    config = tomllib.loads(path.read_text())
    native_consent(config)
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def managed_file_matches(path, relative, digest, manifest):
    if not path.is_file():
        return False
    if relative == 'config.toml' and manifest.get('configuration_sha256'):
        return configuration_digest(path) == manifest['configuration_sha256']
    return sha(path) == digest


def toml_string(value):
    # JSON surrogate-pair escapes are invalid TOML Unicode scalar escapes.
    return json.dumps(value, ensure_ascii=False)


def base_config(layout):
    route = read_json(ROOT / 'config/routing.json')
    q = toml_string
    lines = [f'model = {q(route["quality"]["model"])}',
             f'model_reasoning_effort = {q(route["quality"]["effort"])}',
             'approval_policy = "on-request"', 'sandbox_mode = "workspace-write"',
             'cli_auth_credentials_store = "file"', 'check_for_update_on_startup = false',
             'web_search = "disabled"', 'allow_login_shell = false',
             '[shell_environment_policy]', 'inherit = "core"',
             '[shell_environment_policy.filters]', '"*PASSWORD*" = "exclude"',
             '"*PRIVATE_KEY*" = "exclude"', '"*CREDENTIAL*" = "exclude"',
             '[features]', 'multi_agent = true', 'hooks = true',
             'memories = false', 'plugins = false', 'remote_plugin = false', 'apps = false',
             '[agents]', 'max_concurrent_threads_per_session = 3',
             f'default_subagent_model = {q(route["standard"]["model"])}',
             f'default_subagent_reasoning_effort = {q(route["standard"]["effort"])}']
    for role, tier in [('reviewer', 'quality'), ('security-auditor', 'quality'),
                       ('interop-auditor', 'quality'), ('implementer', 'standard'), ('mechanical', 'mechanical')]:
        lines += [f'[agents.{role}]', f'description = {q(role + ": use Praxis " + tier + " routing; follow Superpowers")}',
                  f'config_file = "agents/{role}.toml"']
        reviewing = role in ('reviewer', 'security-auditor', 'interop-auditor')
        instructions = ('Review only; do not edit the submission. Report blockers with evidence. '
                        'Do not use Engram during workflow review: do not retrieve or persist memory, '
                        'create session summaries, or resolve memory conflicts. '
                        'Inspect the current submission and verification evidence, then return the '
                        'complete review as your final answer, including limitations. '
                        'A progress message to the parent does not replace the final review.'
                        if reviewing else
                        'Implement the assigned task following Superpowers, including tests and review evidence.')
        atomic(layout.codex / 'agents' / (role + '.toml'),
               f'model = {q(route[tier]["model"])}\nmodel_reasoning_effort = {q(route[tier]["effort"])}\n'
               f'developer_instructions = {q(instructions)}\n')
    lines += ['[mcp_servers.engram]', f'command = {q(str(layout.executable("engram")))}',
              'args = ["mcp", "--tools=agent"]', 'required = false',
              '[mcp_servers.openaiDeveloperDocs]', 'url = "https://developers.openai.com/mcp"']
    return '\n'.join(lines) + '\n'


def configure(layout):
    marker = layout.codex / 'praxis-install.json'
    check_ownership(layout)
    config_path = layout.codex / 'config.toml'
    projects, hook_states = native_consent(tomllib.loads(config_path.read_text())) if config_path.exists() else ({}, {})
    layout.codex.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        write_json(marker, {'readiness': 'installation-in-progress'})
    # Gentle writes the Engram integration and persists an infrastructure-only selection.
    env = layout.env()
    env['PATH'] = os.pathsep.join([str(layout.executable(n).parent) for n in ('codex', 'engram', 'gentle-ai')]) + os.pathsep + env['PATH']
    run([layout.executable('gentle-ai'), 'install', '--agents', 'codex', '--preset', 'custom',
         '--components', 'engram', '--persona', 'custom', '--channel', 'stable'],
        env=env, timeout=180)
    generated = layout.codex / 'AGENTS.md'
    memory_path = layout.codex / 'engram-instructions.md'
    memory = memory_path.read_text() if memory_path.exists() else ''
    if any(s in memory for s in ('gentle-ai:sdd', 'gentle-ai:persona', 'gentle-ai:gga')):
        raise PraxisError('Gentle unexpectedly injected an overlapping workflow')
    # Preserve upstream memory guidance, not its base-instruction/compaction replacement.
    config = base_config(layout)
    for path, value in projects.items():
        config += f'\n[projects.{toml_string(path)}]\ntrust_level = {toml_string(value["trust_level"])}\n'
    for key, value in hook_states.items():
        config += f'\n[hooks.state.{toml_string(key)}]\ntrusted_hash = {toml_string(value["trusted_hash"])}\n'
    atomic(config_path, config)
    atomic(generated, (ROOT / 'config/policy.md').read_text() + '\n' + memory)
    for name in ('sdd-strong.config.toml', 'sdd-mid.config.toml', 'sdd-cheap.config.toml'):
        path = layout.codex / name
        if path.exists():
            path.unlink()  # Owned profiles generated by this installation only.
    hooks_dir = layout.codex / 'praxis-hooks'; hooks_dir.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'praxis/hook.py', hooks_dir / 'hook.py')
    shutil.copy2(ROOT / 'praxis/project.py', hooks_dir / 'project.py')
    write_json(hooks_dir / 'routing.json', read_json(ROOT / 'config/routing.json'))
    write_json(hooks_dir / 'project.json', layout.project_options())
    command = shlex.join([sys.executable, str(hooks_dir / 'hook.py')])
    write_json(layout.codex / 'hooks.json', {'hooks': {
        'SessionStart': [{'matcher': 'startup|resume|clear|compact', 'hooks': [{'type': 'command', 'command': command}]}],
        'PreToolUse': [{'matcher': '.*', 'hooks': [{'type': 'command', 'command': command}]}]}})
    link(layout.home / '.agents/skills/superpowers', layout.component('superpowers') / 'skills')
    paths = [layout.codex / 'config.toml', generated, layout.codex / 'hooks.json',
             *[hooks_dir / name for name in ('hook.py', 'project.py', 'routing.json', 'project.json')],
             *(layout.codex / 'agents').glob('*.toml')]
    write_json(marker, {'lock_sha256': sha(ROOT / 'versions.lock.json'),
                        'configuration_sha256': configuration_digest(layout.codex / 'config.toml'),
                        'files': {str(p.relative_to(layout.codex)): sha(p) for p in paths},
                        'integration_sources': {str(p.relative_to(ROOT)): sha(p) for p in
                            [*sorted((ROOT / 'praxis').glob('*.py')), *sorted((ROOT / 'config').glob('*'))] if p.is_file()},
                        'superpowers_skill_files': tree_hashes(layout.component('superpowers') / 'skills'),
                        'readiness': 'self-test-required'})


def bootstrap(layout, *, authenticate=True):
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise PraxisError('This lockfile supports Linux x86-64 only')
    # Check before downloading or changing existing launchers.
    check_ownership(layout)
    require_cutover_resolution(layout)
    for name in layout.lock['components']:
        install_component(layout, name)
    for name in ('codex', 'gentle-ai', 'engram'):
        link(layout.bin / name, layout.executable(name))
    configure(layout)
    if authenticate:
        import subprocess
        status = subprocess.run([str(layout.executable('codex')), 'login', 'status'], env=layout.env(), capture_output=True, text=True)
        if status.returncode:
            run([layout.executable('codex'), 'login', '--device-auth'], env=layout.env(), capture=False, timeout=600)


def doctor(layout):
    errors = []
    marker = layout.codex / 'praxis-install.json'
    if not marker.exists():
        return {'ready': False, 'errors': ['Praxis is not installed']}
    manifest = read_json(marker)
    if 'files' not in manifest:
        return {'ready': False, 'errors': ['Installation incomplete; rerun bootstrap'], 'self_test_required': True}
    errors.extend(installed_errors(layout))
    for relative, digest in manifest.get('integration_sources', {}).items():
        if not (ROOT / relative).is_file() or sha(ROOT / relative) != digest:
            errors.append('Integration source changed; bootstrap and retest: ' + relative)
    for relative, digest in manifest['files'].items():
        path = layout.codex / relative
        if not managed_file_matches(path, relative, digest, manifest):
            errors.append('Managed configuration drift: ' + relative)
    skills = layout.home / '.agents/skills/superpowers'
    if (not skills.is_symlink() or skills.resolve() != (layout.component('superpowers') / 'skills').resolve()
            or manifest.get('superpowers_skill_files') != tree_hashes(skills)):
        errors.append('Pinned Superpowers skill discovery changed')
    for groups in read_json(layout.codex / 'hooks.json').get('hooks', {}).values():
        for group in groups:
            for hook in group['hooks']:
                args = shlex.split(hook['command'])
                expected = manifest['files'].get('praxis-hooks/hook.py')
                if len(args) != 2 or not Path(args[1]).is_file() or sha(args[1]) != expected:
                    errors.append('Referenced hook script differs from approved code')
    for name in layout.lock['components']:
        try:
            if not verify_component(layout, name):
                errors.append('Missing or incomplete ' + name)
        except PraxisError as error:
            errors.append(str(error))
    config = tomllib.loads((layout.codex / 'config.toml').read_text())
    for forbidden in ('model_instructions_file', 'experimental_compact_prompt_file'):
        if forbidden in config:
            errors.append('Conflicting instruction override: ' + forbidden)
    if manifest['lock_sha256'] != sha(ROOT / 'versions.lock.json'):
        errors.append('Installed lockfile differs from repository')
    readiness = layout.state / 'readiness.json'
    passed = read_json(readiness) if readiness.exists() else {}
    valid_test = (passed.get('ready') is True and passed.get('lock_sha256') == sha(ROOT / 'versions.lock.json')
                  and passed.get('installation_sha256') == sha(marker))
    return {'ready': not errors and valid_test, 'errors': errors, 'self_test_required': not valid_test}
