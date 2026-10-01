"""Explicit, terminal-only reset. No automatic application from bootstrap."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import time

from .core import PraxisError, atomic, read_json, run, sha, write_json


def active_codex():
    found = []
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            name = path.read_text().strip()
            if name in ('codex', 'codex-code-mode', 'codex-app-serve'):
                found.append(int(path.parent.name))
        except (FileNotFoundError, PermissionError):
            continue
    return found


def shell_conflicts(home):
    results = []
    for filename in ('.bashrc', '.bash_profile', '.profile', '.zshrc', '.zprofile', '.config/fish/config.fish'):
        path = home / filename
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.lstrip().startswith('#') and any(s in line for s in ('agentcore', 'CODEX_HOME', 'alias codex', 'function codex')):
                # Never include shell contents: lines may contain credentials.
                results.append({'path': str(path), 'line': number})
    return results


def targets(layout):
    return [layout.codex, layout.home / '.agents/skills',
            layout.home / '.config/gentle-ai', layout.home / '.local/share/gentle-ai',
            layout.home / '.local/share/gga',
            *[layout.bin / name for name in ('codex', 'gentle-ai', 'engram')]]


def fingerprint(path):
    if path.is_symlink():
        return {'kind': 'symlink', 'target': str(path.readlink())}
    if not path.exists():
        return {'kind': 'absent'}
    # Runtime SQLite/logs may change during inventory. Hash configuration only.
    files = {}
    if path.is_dir():
        for p in path.rglob('*'):
            if p.is_symlink():
                files[str(p.relative_to(path))] = {'target': str(p.readlink()),
                    'sha256': sha(p) if p.is_file() else None}
            elif p.is_file() and p.name != 'auth.json' and p.suffix in ('.toml', '.md', '.rules', '.json', '.py', '.sh', '.js'):
                files[str(p.relative_to(path))] = sha(p)
    else:
        files[path.name] = sha(path)
    return {'kind': 'directory' if path.is_dir() else 'file', 'configuration_sha256': files}


def inventory(layout):
    layout.state.mkdir(parents=True, exist_ok=True)
    values = {str(p): fingerprint(p) for p in targets(layout)}
    blockers = []
    conflicts = shell_conflicts(layout.home)
    if conflicts:
        blockers.append({'reason': 'Shell customizations need explicit manual removal', 'locations': conflicts})
    if any(p.is_symlink() for p in targets(layout) if p.parent != layout.bin):
        blockers.append({'reason': 'Customization root is a symlink; resolve ownership manually'})
    if Path('/etc/codex').exists():
        blockers.append({'reason': 'System-managed /etc/codex requires separate inspection; never erase it'})
    # Known previous evaluation units must not auto-start after the reset.
    services = []
    for p in (layout.home / '.config/systemd/user').glob('*'):
        if p.is_file() and p.suffix in ('.service', '.timer'):
            content = p.read_text(errors='replace')
            if any(s in content for s in ('agentcore', 'codex', 'gentle-ai')):
                services.append({'name': p.name, 'sha256': sha(p)})
    value = {'schema_version': 1, 'home': str(layout.home), 'targets': values,
             'blockers': blockers, 'services': services, 'active_codex_pids': active_codex(),
             'effect': 'Archive all user Codex customizations, preserve auth, disable inventoried services; bootstrap separately'}
    destination = layout.state / ('cutover-inventory-' + str(time.time_ns()) + '.json')
    write_json(destination, value)
    return {'inventory': str(destination), **value}


def apply(layout, inventory_path):
    if not os.isatty(0) or os.environ.get('CODEX_THREAD_ID') or active_codex():
        raise PraxisError('Cutover requires a standalone terminal with every Codex session/process closed.')
    reviewed = read_json(inventory_path)
    if reviewed['home'] != str(layout.home) or reviewed['blockers']:
        raise PraxisError('Inventory has blockers or belongs to another home')
    if set(reviewed['targets']) != {str(p) for p in targets(layout)}:
        raise PraxisError('Inventory target set differs from the fixed reset scope')
    for p in targets(layout):
        if fingerprint(p) != reviewed['targets'][str(p)]:
            raise PraxisError('Customization changed since inventory; regenerate inventory: ' + str(p))
    if shell_conflicts(layout.home):
        raise PraxisError('Shell customization changed; inspect a new inventory')
    if input('Type RESET CODEX to archive all customizations: ') != 'RESET CODEX':
        raise PraxisError('Cutover not confirmed')
    archive = layout.state / ('cutover-backup-' + str(time.time_ns()))
    archive.mkdir(mode=0o700, parents=True)
    write_json(archive / 'inventory.json', reviewed)
    with (layout.state / 'cutover.lock').open('w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if active_codex():
            raise PraxisError('Codex started during confirmation; refusing cutover')
        for p in targets(layout):
            if fingerprint(p) != reviewed['targets'][str(p)]:
                raise PraxisError('Customization changed during confirmation')
        service_states = []
        for unit in reviewed['services']:
            source = layout.home / '.config/systemd/user' / unit['name']
            if '/' in unit['name'] or sha(source) != unit['sha256']:
                raise PraxisError('Service changed since inventory')
            service_states.append({'name': unit['name'],
                'before': run(['systemctl', '--user', 'show', unit['name'],
                    '--property=ActiveState,UnitFileState'])})
        write_json(archive / 'service-journal.json', service_states)
        moved = []
        move_journal = []
        write_json(archive / 'moves.json', move_journal)
        try:
            for unit in service_states:
                unit['intent'] = 'disable --now'
                write_json(archive / 'service-journal.json', service_states)
                run(['systemctl', '--user', 'disable', '--now', unit['name']])
                unit['completed'] = True
                write_json(archive / 'service-journal.json', service_states)
            for p in targets(layout):
                if p.exists() or p.is_symlink():
                    dest = archive / p.relative_to(layout.home)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    item = {'source': str(p), 'destination': str(dest), 'completed': False}
                    move_journal.append(item)
                    write_json(archive / 'moves.json', move_journal)
                    p.rename(dest)
                    moved.append((p, dest))
                    item['completed'] = True
                    write_json(archive / 'moves.json', move_journal)
            layout.codex.mkdir(mode=0o700, parents=True, exist_ok=True)
            auth = archive / '.codex/auth.json'
            if auth.is_file() and not auth.is_symlink():
                # Keep credentials local, out of repository and out of printed evidence.
                shutil.copy2(auth, layout.codex / 'auth.json')
                os.chmod(layout.codex / 'auth.json', 0o600)
            extras = [p.name for p in layout.codex.iterdir() if p.name != 'auth.json']
            if extras:
                raise PraxisError('Clean baseline has unexpected entries')
            write_json(archive / 'clean-baseline.json', {'customizations': [], 'credentials_preserved': (layout.codex / 'auth.json').exists()})
        except BaseException:
            write_json(archive / 'recovery-required.json', {'message': 'Inspect moves.json. Do not blindly overwrite any new files.'})
            raise
    return {'clean': True, 'backup': str(archive), 'next': 'Run Praxis bootstrap from the standalone terminal; then self-test.'}
