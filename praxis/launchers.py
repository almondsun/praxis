"""Read-only ownership checks; never run competing launchers or shell startup."""
import os
from pathlib import Path
import re
import tomllib

from .core import PraxisError, sha


def shell_conflicts(home):
    results = []
    sources = {home / filename for filename in ('.bashrc', '.bash_profile', '.bash_login',
               '.bash_aliases', '.profile', '.zshrc', '.zprofile', '.zshenv', '.zlogin',
               '.config/zsh/.zshrc', '.config/zsh/.zshenv', '.config/fish/config.fish')}
    config_roots = {home / '.config'}
    if home == Path.home().resolve():
        if os.environ.get('XDG_CONFIG_HOME'):
            config_roots.add(Path(os.environ['XDG_CONFIG_HOME']))
        for name in ('BASH_ENV', 'ENV'):
            if os.environ.get(name):
                sources.add(Path(os.environ[name]).expanduser())
        if os.environ.get('ZDOTDIR'):
            sources.update(Path(os.environ['ZDOTDIR']) / filename for filename in
                           ('.zshrc', '.zprofile', '.zshenv', '.zlogin'))
    for directory in config_roots:
        sources.add(directory / 'fish/config.fish')
        sources.update((directory / 'fish/conf.d').glob('*.fish'))
        autoload = directory / 'fish/functions/codex.fish'
        if autoload.exists() or autoload.is_symlink():
            results.append({'path': str(autoload), 'line': 1})
    for source in sorted(sources):
        if not source.is_file():
            continue
        for number, line in enumerate(source.read_text().splitlines(), 1):
            if not line.lstrip().startswith('#') and (any(s in line for s in ('agentcore', 'CODEX_HOME'))
                    or re.search(r'\balias\s+(?:--\s+)?[\"\x27]?codex\b|\bfunction\s+codex\b|\bcodex\s*\(\s*\)', line)):
                # Report locations, never shell contents that might contain secrets.
                results.append({'path': str(source), 'line': number})
    return results


def search_path(layout):
    # Disposable installs must not inherit the active user's tool managers.
    return (os.environ.get('PATH', os.defpath) if layout.home == Path.home().resolve()
            else layout.env()['PATH'])


def resolution(layout):
    path = search_path(layout)
    expected = layout.executable('codex').resolve()
    owned = layout.bin.resolve() / 'codex'
    entries = []
    blockers = []
    seen = set()
    for directory in path.split(os.pathsep):
        candidate = Path(directory or '.').resolve() / 'codex'
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            continue
        resolved = candidate.resolve()
        entries.append({'path': str(candidate), 'resolved': str(resolved),
                        'sha256': sha(candidate)})
        # Only the reset-owned launcher or the exact pinned executable is allowed.
        if candidate != owned and resolved != expected:
            blockers.append({'reason': 'Competing Codex executable on PATH', 'path': str(candidate)})
    if not any(Path(p or '.').resolve() == layout.bin.resolve() for p in path.split(os.pathsep)):
        blockers.append({'reason': 'Praxis launcher directory is absent from PATH', 'path': str(layout.bin)})

    config_root = layout.home / '.config'
    configs = set()
    def add_directory(directory):
        configs.update(directory.glob('config*.toml'))
        configs.update(directory.glob('mise*.toml'))
        configs.update(directory.glob('conf.d/**/*.toml'))
    add_directory(config_root / 'mise')
    add_directory(Path('/etc/mise'))
    configs.update(layout.home.glob('.mise*.toml'))
    configs.add(layout.home / '.tool-versions')
    # Local tool-manager configuration can reactivate Codex when entering a repo.
    for parent in (Path.cwd(), *Path.cwd().parents):
        if parent == Path.home().resolve() and parent != layout.home:
            # An isolated home never imports the real user's global configuration.
            continue
        configs.update(parent / name for name in ('mise.toml', '.mise.toml',
                       'mise.local.toml', '.mise.local.toml', '.config/mise.toml'))
        configs.update(parent.glob('mise.*.toml'))
        configs.update(parent.glob('.mise.*.toml'))
        configs.add(parent / '.tool-versions')
        configs.update((parent / '.config').glob('mise*.toml'))
        for name in ('.config/mise', '.mise', 'mise'):
            add_directory(parent / name)
    if layout.home == Path.home().resolve():
        for name in ('MISE_CONFIG_FILE', 'MISE_GLOBAL_CONFIG_FILE'):
            if os.environ.get(name):
                configs.add(Path(os.environ[name]).expanduser().absolute())
        if os.environ.get('XDG_CONFIG_HOME'):
            add_directory(Path(os.environ['XDG_CONFIG_HOME']) / 'mise')
        if os.environ.get('MISE_CONFIG_DIR'):
            add_directory(Path(os.environ['MISE_CONFIG_DIR']))
        if os.environ.get('MISE_SYSTEM_CONFIG_DIR'):
            add_directory(Path(os.environ['MISE_SYSTEM_CONFIG_DIR']))
        if os.environ.get('MISE_CODEX_VERSION'):
            blockers.append({'reason': 'Mise Codex version environment override', 'variable': 'MISE_CODEX_VERSION'})
        for name in ('MISE_DEFAULT_CONFIG_FILENAME', 'MISE_DEFAULT_TOOL_VERSIONS_FILENAME',
                     'MISE_OVERRIDE_CONFIG_FILENAMES', 'MISE_OVERRIDE_TOOL_VERSIONS_FILENAMES'):
            if os.environ.get(name):
                blockers.append({'reason': 'Custom Mise discovery requires explicit ownership review', 'variable': name})
        if 'BASH_FUNC_codex%%' in os.environ:
            blockers.append({'reason': 'Exported Codex shell function', 'variable': 'BASH_FUNC_codex%%'})
    records = []
    for source in sorted(configs):
        if not source.is_file():
            continue
        records.append({'path': str(source), 'sha256': sha(source)})
        try:
            if source.name == '.tool-versions':
                if any(re.search(r'(^|[:/])codex$', line.split()[0]) for line in source.read_text().splitlines()
                       if line.strip() and not line.lstrip().startswith('#')):
                    blockers.append({'reason': 'Mise/asdf manages Codex via .tool-versions', 'path': str(source)})
                continue
            config = tomllib.loads(source.read_text())
            tools = config.get('tools', {})
            if not isinstance(tools, dict):
                raise ValueError('Invalid tools table')
            if any(re.search(r'(^|[:/])codex$', key) for key in tools):
                blockers.append({'reason': 'Mise manages Codex; explicitly remove its Codex ownership',
                                 'path': str(source)})
            aliases = config.get('shell_alias', {})
            if not isinstance(aliases, dict):
                raise ValueError('Invalid shell_alias table')
            if 'codex' in aliases:
                blockers.append({'reason': 'Mise defines a Codex shell alias', 'path': str(source)})
        except (OSError, ValueError):
            blockers.append({'reason': 'Cannot inspect Mise configuration', 'path': str(source)})
    conflicts = shell_conflicts(layout.home)
    if conflicts:
        blockers.append({'reason': 'Shell customizations need explicit manual removal', 'locations': conflicts})
    return {'path': path, 'executables': entries, 'mise_configuration': records,
            'expected': str(expected), 'blockers': blockers}


def require_cutover_resolution(layout, reviewed=None):
    current = resolution(layout)
    if current['blockers']:
        raise PraxisError('Codex launcher ownership blocks cutover: ' + str(current['blockers']))
    if reviewed is not None and current != reviewed:
        raise PraxisError('Codex launcher resolution changed since inventory; regenerate inventory')
    return current


def installed_errors(layout):
    current = resolution(layout)
    errors = [str(blocker) for blocker in current['blockers']]
    launcher = layout.bin / 'codex'
    if not launcher.is_symlink() or launcher.resolve() != layout.executable('codex').resolve():
        errors.append('Praxis Codex launcher does not point to the pinned binary')
    entries = current['executables']
    if not entries or entries[0]['resolved'] != current['expected']:
        errors.append('Ordinary codex does not resolve to the Praxis-pinned binary')
    return errors
