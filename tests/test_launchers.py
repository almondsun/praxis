import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from praxis.core import Layout, PraxisError, atomic, read_json, sha, write_json
from praxis.cutover import apply, inventory, shell_conflicts
from praxis.install import bootstrap, configure, doctor
from praxis.launchers import installed_errors, resolution, require_cutover_resolution


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.layout = Layout(self.temporary.name)
        self.path = str(self.layout.bin)
        self.override = patch('praxis.launchers.search_path', side_effect=lambda _: self.path)
        self.override.start()
        self.addCleanup(self.override.stop)

    def executable(self, path, text='#!/bin/sh\nexit 0\n'):
        atomic(path, text, mode=0o755)

    def mise(self, text='[tools]\ncodex = "latest"\n'):
        path = self.layout.home / '.config/mise/config.toml'
        atomic(path, text)
        return path

    def test_higher_priority_mise_latest_is_inventory_blocker_without_execution(self):
        mise = self.mise()
        competing = self.layout.home / '.local/share/mise/installs/codex/latest/bin/codex'
        self.executable(competing, '#!/bin/sh\ntouch must-not-run\n')
        self.path = str(competing.parent) + os.pathsep + self.path
        before = sha(mise)
        result = inventory(self.layout)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['launcher_resolution']['executables'][0]['path'], str(competing))
        self.assertEqual(len(result['blockers']), 2)
        self.assertEqual(sha(mise), before)
        self.assertFalse(Path('must-not-run').exists())
        with patch('praxis.cutover.active_codex', return_value=[]), \
                patch('os.isatty', return_value=True), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PraxisError, 'blockers'):
                apply(self.layout, result['inventory'])

    def test_config_and_lower_priority_shim_block_even_with_praxis_first(self):
        pinned = self.layout.executable('codex')
        self.executable(pinned)
        self.layout.bin.mkdir(parents=True, exist_ok=True)
        (self.layout.bin / 'codex').symlink_to(pinned)
        shim = self.layout.home / '.local/share/mise/shims/codex'
        self.executable(shim)
        self.path += os.pathsep + str(shim.parent)
        self.mise('[tools]\n"aqua:openai/codex" = "0.159.2"\n')
        self.assertEqual(len(resolution(self.layout)['blockers']), 2)
        self.assertTrue(installed_errors(self.layout))

    def test_unrelated_mise_tools_untouched_and_exact_pinned_resolution_passes(self):
        config = self.mise('[tools]\npython = "3.14"\nnode = "latest"\n')
        before = sha(config)
        pinned = self.layout.executable('codex')
        self.executable(pinned)
        self.layout.bin.mkdir(parents=True, exist_ok=True)
        (self.layout.bin / 'codex').symlink_to(pinned)
        self.path += os.pathsep + str(self.layout.home / '.local/share/../bin')
        self.assertEqual(installed_errors(self.layout), [])
        require_cutover_resolution(self.layout)
        self.assertEqual(sha(config), before)

    def test_legacy_inventory_and_new_race_cannot_bypass_apply(self):
        current = inventory(self.layout)
        path = Path(current['inventory'])
        reviewed = read_json(path)
        reviewed.pop('launcher_resolution')
        write_json(path, reviewed)
        with patch('praxis.cutover.active_codex', return_value=[]), \
                patch('os.isatty', return_value=True), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PraxisError, 'lacks Codex'):
                apply(self.layout, path)
            reviewed['launcher_resolution'] = current['launcher_resolution']
            write_json(path, reviewed)
            self.mise()
            with patch('builtins.input') as confirm, patch('praxis.cutover.run') as commands:
                with self.assertRaisesRegex(PraxisError, 'ownership blocks'):
                    apply(self.layout, path)
                confirm.assert_not_called()
                commands.assert_not_called()
        self.assertFalse(list(self.layout.state.glob('cutover-backup-*')))

    def test_configuration_added_during_confirmation_blocks_before_moves(self):
        self.executable(self.layout.bin / 'codex')
        current = inventory(self.layout)
        def confirm(_):
            self.mise()
            return 'RESET CODEX'
        with patch('praxis.cutover.active_codex', return_value=[]), \
                patch('os.isatty', return_value=True), patch.dict(os.environ, {}, clear=True), \
                patch('builtins.input', side_effect=confirm), patch('praxis.cutover.run') as commands:
            with self.assertRaisesRegex(PraxisError, 'ownership blocks'):
                apply(self.layout, current['inventory'])
            commands.assert_not_called()
        self.assertTrue((self.layout.bin / 'codex').exists())

    def test_bootstrap_refuses_competing_ownership_before_downloading(self):
        self.mise()
        with patch('praxis.install.install_component') as install:
            with self.assertRaisesRegex(PraxisError, 'ownership blocks'):
                bootstrap(self.layout, authenticate=False)
            install.assert_not_called()

    def test_missing_path_and_malformed_configuration_fail_closed(self):
        self.path = '/usr/bin'
        self.mise('[tools\n')
        self.assertEqual(len(resolution(self.layout)['blockers']), 2)

    def test_shell_functions_and_aliases_are_explicit_blockers_without_disclosure(self):
        atomic(self.layout.home / '.bashrc', 'codex() { echo secret; }\nalias   codex="secret"\n')
        atomic(self.layout.home / '.config/fish/config.fish', 'function codex\n  echo secret\nend\n')
        conflicts = shell_conflicts(self.layout.home)
        self.assertEqual(len(conflicts), 3)
        self.assertNotIn('secret', str(conflicts))
        self.assertTrue(inventory(self.layout)['blockers'])
        with patch('praxis.install.install_component') as download:
            with self.assertRaisesRegex(PraxisError, 'Shell customizations'):
                bootstrap(self.layout, authenticate=False)
            download.assert_not_called()
        self.assertTrue(any('Shell customizations' in error for error in installed_errors(self.layout)))

    def test_shell_override_added_during_confirmation_blocks_reset(self):
        current = inventory(self.layout)
        def confirm(_):
            atomic(self.layout.home / '.bashrc', 'codex() { echo secret; }\n')
            return 'RESET CODEX'
        with patch('praxis.cutover.active_codex', return_value=[]), \
                patch('os.isatty', return_value=True), patch.dict(os.environ, {}, clear=True), \
                patch('builtins.input', side_effect=confirm), patch('praxis.cutover.run') as commands:
            with self.assertRaisesRegex(PraxisError, 'Shell customizations'):
                apply(self.layout, current['inventory'])
            commands.assert_not_called()

    def test_environment_suffixed_mise_configuration_cannot_hide_codex(self):
        atomic(self.layout.home / '.config/mise/config.production.toml', '[tools]\ncodex="latest"\n')
        self.assertTrue(any('Mise manages' in b['reason'] for b in resolution(self.layout)['blockers']))

    def test_system_mise_configuration_is_read_only_blocker(self):
        system = self.layout.home / 'system-mise'
        atomic(system / 'conf.d/codex.toml', '[tools]\ncodex="latest"\n')
        real_glob = Path.glob
        def glob(path, pattern):
            return real_glob(system if path == Path('/etc/mise') else path, pattern)
        with patch.object(Path, 'glob', glob):
            self.assertTrue(any('Mise manages' in b['reason'] for b in resolution(self.layout)['blockers']))

    def test_tool_versions_project_config_and_mise_shell_alias_block(self):
        local = self.layout.home / 'project'
        local.mkdir()
        files = {self.layout.home / '.tool-versions': 'codex latest\npython 3.14\n',
                 local / '.config/mise/config.toml': '[tools]\ncodex="latest"\n',
                 local / 'mise.toml': '[shell_alias]\ncodex="competing --secret"\n'}
        for source, value in files.items():
            atomic(source, value)
        previous = Path.cwd()
        try:
            os.chdir(local)
            current = resolution(self.layout)
            self.assertEqual(len(current['blockers']), 3)
            self.assertNotIn('--secret', str(current))
        finally:
            os.chdir(previous)

    def test_standard_sourced_shell_files_and_fish_autoload_block(self):
        atomic(self.layout.home / '.bash_aliases', 'alias codex="other"\n')
        atomic(self.layout.home / '.zshenv', 'codex() { echo other; }\n')
        atomic(self.layout.home / '.config/fish/functions/codex.fish', 'function codex\nend\n')
        self.assertEqual(len(shell_conflicts(self.layout.home)), 3)

    def test_redirected_xdg_fish_autoload_is_blocker(self):
        xdg = self.layout.home / 'custom-xdg'
        atomic(xdg / 'fish/functions/codex.fish', 'function codex\nend\n')
        with patch('praxis.launchers.Path.home', return_value=self.layout.home), \
                patch.dict(os.environ, {'XDG_CONFIG_HOME': str(xdg)}):
            self.assertEqual(len(shell_conflicts(self.layout.home)), 1)

    def test_real_path_policy_separates_production_and_disposable_homes(self):
        self.override.stop()
        from praxis.launchers import search_path
        with patch('praxis.launchers.Path.home', return_value=self.layout.home), \
                patch.dict(os.environ, {'PATH': '/competing/bin'}):
            self.assertEqual(search_path(self.layout), '/competing/bin')
        with patch.dict(os.environ, {'PATH': '/competing/bin'}):
            self.assertEqual(search_path(self.layout), self.layout.env()['PATH'])

    def test_alias_options_exported_functions_and_discovery_overrides_block(self):
        atomic(self.layout.home / '.bashrc', 'alias -- codex="other"\n')
        self.assertEqual(len(shell_conflicts(self.layout.home)), 1)
        with patch('praxis.launchers.Path.home', return_value=self.layout.home), \
                patch.dict(os.environ, {'BASH_FUNC_codex%%': '() { secret; }',
                          'MISE_OVERRIDE_CONFIG_FILENAMES': 'hidden.toml'}):
            current = resolution(self.layout)
        self.assertTrue(any(b.get('variable') == 'BASH_FUNC_codex%%' for b in current['blockers']))
        self.assertTrue(any(b.get('variable') == 'MISE_OVERRIDE_CONFIG_FILENAMES' for b in current['blockers']))
        self.assertNotIn('secret', str(current))

    def test_alternate_project_mise_layouts_and_grouped_configs_block(self):
        local = self.layout.home / 'project'
        local.mkdir()
        names = ('.config/mise.local.toml', '.config/mise/mise.toml',
                 '.config/mise/mise.local.toml', '.mise/config.local.toml',
                 'mise/config.local.toml', '.config/mise/conf.d/group/codex.toml')
        for name in names:
            atomic(local / name, '[tools]\ncodex="latest"\n')
        previous = Path.cwd()
        try:
            os.chdir(local)
            self.assertEqual(len(resolution(self.layout)['blockers']), len(names))
        finally:
            os.chdir(previous)

    def test_local_mise_config_and_changed_path_invalidate_inventory(self):
        current = resolution(self.layout)
        self.path += os.pathsep + str(self.layout.home / 'new-bin')
        with self.assertRaisesRegex(PraxisError, 'changed since inventory'):
            require_cutover_resolution(self.layout, current)
        local = self.layout.home / 'project'
        local.mkdir()
        atomic(local / 'mise.toml', '[tools]\ncodex="latest"\n')
        previous = Path.cwd()
        try:
            os.chdir(local)
            self.assertTrue(any('Mise manages' in b['reason'] for b in resolution(self.layout)['blockers']))
        finally:
            os.chdir(previous)

    def test_doctor_rejects_drift_even_with_hash_bound_passed_selftest(self):
        (self.layout.component('superpowers') / 'skills').mkdir(parents=True)
        self.executable(self.layout.executable('codex'))
        self.layout.bin.mkdir(parents=True)
        (self.layout.bin / 'codex').symlink_to(self.layout.executable('codex'))
        with patch('praxis.install.run'):
            configure(self.layout)
        marker = self.layout.codex / 'praxis-install.json'
        from praxis.core import ROOT
        write_json(self.layout.state / 'readiness.json', {'ready': True,
                   'lock_sha256': sha(ROOT / 'versions.lock.json'), 'installation_sha256': sha(marker)})
        with patch('praxis.install.verify_component', return_value=True):
            self.assertTrue(doctor(self.layout)['ready'])
            self.mise()
            result = doctor(self.layout)
        self.assertFalse(result['ready'])
        self.assertFalse(result['self_test_required'])
        self.assertTrue(any('Mise manages Codex' in error for error in result['errors']))
