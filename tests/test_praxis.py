import io
import json
from pathlib import Path
import tarfile
import tempfile
import tomllib
import unittest
from unittest.mock import Mock, patch

from praxis.core import Layout, PraxisError, atomic, read_json, write_json
from praxis.cutover import apply, fingerprint, shell_conflicts, targets
from praxis.hook import respond
from praxis.install import base_config, bootstrap, configure, doctor, unpack, configuration_digest
from praxis.session import execute, infrastructure_errors
from praxis.selftest import runtime_evidence, require_regression_evidence


class PraxisTests(unittest.TestCase):
    def test_native_hook_consent_is_normalized_but_execution_edits_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.toml'
            atomic(path, 'model="q"\n')
            before = configuration_digest(path)
            consent = '[hooks.state."path:fixture"]\ntrusted_hash="sha256:' + 'a' * 64 + '"\n'
            atomic(path, 'model="q"\n' + consent)
            self.assertEqual(configuration_digest(path), before)
            atomic(path, 'model="changed"\n' + consent)
            self.assertNotEqual(configuration_digest(path), before)
            for extra in ('enabled=false\n', 'unknown=true\n'):
                atomic(path, 'model="q"\n' + consent + extra)
                with self.assertRaises(PraxisError):
                    configuration_digest(path)
            atomic(path, 'model="q"\n[hooks.state."path:fixture"]\ntrusted_hash="invalid"\n')
            with self.assertRaises(PraxisError):
                configuration_digest(path)

    def test_reconfiguration_preserves_native_consent(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            atomic(layout.codex / 'config.toml', 'model="q"\n[projects."/tmp/project-🚀"]\ntrust_level="trusted"\n'
                   '[hooks.state."path:fixture-🚀"]\ntrusted_hash="sha256:' + 'a' * 64 + '"\n')
            with patch('praxis.install.check_ownership'), patch('praxis.install.run'):
                configure(layout)
            config = tomllib.loads((layout.codex / 'config.toml').read_text())
            self.assertEqual(config['projects']['/tmp/project-🚀']['trust_level'], 'trusted')
            self.assertEqual(config['hooks']['state']['path:fixture-🚀']['trusted_hash'], 'sha256:' + 'a' * 64)
            self.assertEqual(configuration_digest(layout.codex / 'config.toml'),
                             read_json(layout.codex / 'praxis-install.json')['configuration_sha256'])

    def test_independent_review_roles_request_readonly_and_disable_engram(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            base_config(layout)
            for role in ('reviewer', 'security-auditor', 'interop-auditor'):
                config = tomllib.loads((layout.codex / 'agents' / (role + '.toml')).read_text())
                self.assertEqual(config['sandbox_mode'], 'read-only')
                self.assertFalse(config['mcp_servers']['engram']['enabled'])
                self.assertEqual(config['model'], 'gpt-6-astra')
                self.assertEqual(config['model_reasoning_effort'], 'high')
            config = tomllib.loads((layout.codex / 'agents' / 'implementer.toml').read_text())
            self.assertNotIn('mcp_servers', config)
            self.assertNotIn('sandbox_mode', config)

    def test_nonempty_regression_gate_requires_real_failures_and_success(self):
        require_regression_evidence('Ran 9 tests in 0.1s\n\nOK\n')
        require_regression_evidence('Ran 9 tests in 0.1s\n\nFAILED (failures=7)\n', red=True)
        for output, red in [('Ran 0 tests in 0.0s\nOK\n', False),
                            ('Ran 1 test in 0.1s\nFAILED (errors=1)\n', True),
                            ('Ran 9 tests in 0.1s\nOK\n', True)]:
            with self.subTest(output=output), self.assertRaises(PraxisError):
                require_regression_evidence(output, red=red)

    def test_production_has_no_deadline_and_control_deadline_is_recorded(self):
        for deadline in (None, 1):
            with self.subTest(deadline=deadline), tempfile.TemporaryDirectory() as tmp:
                layout = Layout(tmp); evidence = Path(tmp) / 'evidence'
                process = Mock(); process.pid = 123
                process.poll.side_effect = [None, 0]
                process.wait.return_value = 0
                with patch('praxis.install.doctor', return_value={'errors': []}), \
                        patch('praxis.session.subprocess.Popen', return_value=process), \
                        patch('praxis.session.time.monotonic', side_effect=[0, 1000, 1001]), \
                        patch('praxis.session.time.sleep'), patch('praxis.session.os.killpg') as terminate:
                    if deadline is None:
                        result = execute(layout, Path(tmp), 'fixture', 'phase', evidence, readonly=True)
                        self.assertFalse(result['timed_out'])
                        terminate.assert_not_called()
                    else:
                        with self.assertRaises(PraxisError):
                            execute(layout, Path(tmp), 'fixture', 'phase', evidence, readonly=True, timeout=deadline)
                        result = read_json(evidence / 'phase-result.json')
                        self.assertTrue(result['timed_out'])
                        self.assertTrue(result['manual_resume_required'])
                        self.assertEqual(result['stop_reason'], 'phase_deadline')
                        terminate.assert_called_once()

    def test_successful_diagnostic_text_is_not_runtime_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'log.jsonl'
            log.write_text(json.dumps({'type': 'item.completed', 'item': {
                'type': 'command_execution', 'status': 'completed', 'exit_code': 0,
                'command': "printf 'read-only file system'", 'aggregated_output': 'read-only file system'}}))
            self.assertEqual(infrastructure_errors(log), [])
            log.write_text(json.dumps({'type': 'item.completed', 'item': {
                'type': 'command_execution', 'status': 'failed', 'exit_code': 1,
                'command': 'inspect read-only file system', 'aggregated_output': 'ordinary assertion failure'}}))
            self.assertEqual(infrastructure_errors(log), [])
            log.write_text(json.dumps({'type': 'turn.failed', 'error': {'message': 'Server connection closed unexpectedly'}}))
            self.assertEqual(len(infrastructure_errors(log)), 1)
    def test_runtime_gate_rejects_main_downgrade_and_remote_skills(self):
        for model, remote in [('gpt-6.1-sol', False), ('gpt-6-astra', True)]:
            with self.subTest(model=model, remote=remote), tempfile.TemporaryDirectory() as tmp:
                layout = Layout(tmp)
                rows = [
                    {'type': 'session_meta', 'payload': {'source': 'exec'}},
                    {'type': 'turn_context', 'payload': {'model': model,
                        'effort': 'medium' if model == 'gpt-6.1-sol' else 'high'}},
                    {'type': 'response_item', 'payload': {'role': 'developer',
                        'content': 'Available skills: using-superpowers' +
                        (' openai-curated-remote' if remote else '')}}]
                atomic(layout.codex / 'sessions/fixture.jsonl',
                       '\n'.join(json.dumps(row) for row in rows))
                archive = Path(tmp) / 'archive'; archive.mkdir()
                with self.assertRaisesRegex(PraxisError, 'Role routing or native skill isolation'):
                    runtime_evidence(layout, archive)
                self.assertTrue((archive / 'sessions/fixture.jsonl').exists())
                self.assertTrue((archive / 'runtime-models.json').exists())

    def test_only_native_project_trust_is_excluded_from_config_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.toml'
            atomic(path, 'model="q"\n')
            before = configuration_digest(path)
            atomic(path, 'model="q"\n[projects."/tmp/task"]\ntrust_level="trusted"\n')
            self.assertEqual(configuration_digest(path), before)
            atomic(path, 'model="changed"\n[projects."/tmp/task"]\ntrust_level="trusted"\n')
            self.assertNotEqual(configuration_digest(path), before)
            atomic(path, 'model="q"\n[projects."/tmp/task"]\ntrust_level="trusted"\nmodel="changed"\n')
            with self.assertRaises(PraxisError):
                configuration_digest(path)
    def test_fixture_git_environment_cannot_inherit_host_overrides(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'GIT_DIR': '/wrong', 'GIT_CONFIG_GLOBAL': '/wrong'}):
            env = Layout(tmp).fixture_env()
            self.assertNotIn('GIT_DIR', env)
            self.assertEqual(env['GIT_CONFIG_GLOBAL'], '/dev/null')
            self.assertEqual(env['GIT_CONFIG_VALUE_0'], '/dev/null')
            self.assertEqual(env['GIT_CONFIG_VALUE_1'], 'false')

    def test_inventory_covers_launchers_and_executable_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            self.assertIn(layout.bin / 'codex', targets(layout))
            atomic(layout.codex / 'hooks.json', '{}')
            atomic(layout.codex / 'hook.py', 'print(1)')
            before = fingerprint(layout.codex)
            atomic(layout.codex / 'hook.py', 'print(2)')
            self.assertNotEqual(before, fingerprint(layout.codex))

    def test_cutover_rechecks_processes_after_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            path = Path(tmp) / 'inventory.json'
            write_json(path, {'home': str(layout.home), 'blockers': [], 'services': [],
                'targets': {str(p): fingerprint(p) for p in targets(layout)}})
            with patch('os.isatty', return_value=True), patch.dict('os.environ', {}, clear=True), \
                    patch('praxis.cutover.active_codex', side_effect=[[], [123]]), \
                    patch('builtins.input', return_value='RESET CODEX'):
                with self.assertRaisesRegex(PraxisError, 'during confirmation'):
                    apply(layout, path)
            self.assertFalse(layout.codex.exists())

    def test_stale_second_service_cannot_disable_first_service(self):
        from praxis.core import sha
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            units = layout.home / '.config/systemd/user'
            atomic(units / 'first.service', 'first')
            atomic(units / 'second.service', 'second')
            path = Path(tmp) / 'inventory.json'
            write_json(path, {'home': str(layout.home), 'blockers': [],
                'services': [{'name': name, 'sha256': sha(units / name)}
                    for name in ('first.service', 'second.service')],
                'targets': {str(p): fingerprint(p) for p in targets(layout)}})
            atomic(units / 'second.service', 'changed')
            with patch('os.isatty', return_value=True), patch.dict('os.environ', {}, clear=True), \
                    patch('praxis.cutover.active_codex', return_value=[]), \
                    patch('builtins.input', return_value='RESET CODEX'), \
                    patch('praxis.cutover.run', return_value='ActiveState=inactive') as command:
                with self.assertRaisesRegex(PraxisError, 'Service changed'):
                    apply(layout, path)
            self.assertTrue(all('disable' not in call.args[0] for call in command.call_args_list))

    def test_cutover_archives_launcher_and_preserves_local_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            atomic(layout.codex / 'config.toml', 'model="old"')
            atomic(layout.codex / 'auth.json', '{"fixture":true}')
            atomic(layout.bin / 'codex', 'old launcher')
            path = Path(tmp) / 'inventory.json'
            write_json(path, {'home': str(layout.home), 'blockers': [], 'services': [],
                'targets': {str(p): fingerprint(p) for p in targets(layout)}})
            with patch('os.isatty', return_value=True), patch.dict('os.environ', {}, clear=True), \
                    patch('praxis.cutover.active_codex', return_value=[]), \
                    patch('builtins.input', return_value='RESET CODEX'):
                result = apply(layout, path)
            archive = Path(result['backup'])
            self.assertEqual((archive / '.local/bin/codex').read_text(), 'old launcher')
            self.assertFalse((layout.bin / 'codex').exists())
            self.assertEqual([p.name for p in layout.codex.iterdir()], ['auth.json'])
            self.assertTrue(all(x['completed'] for x in read_json(archive / 'moves.json')))

    def test_cutover_interrupt_preserves_move_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            atomic(layout.codex / 'config.toml', 'model="old"')
            path = Path(tmp) / 'inventory.json'
            write_json(path, {'home': str(layout.home), 'blockers': [], 'services': [],
                'targets': {str(p): fingerprint(p) for p in targets(layout)}})
            with patch('os.isatty', return_value=True), patch.dict('os.environ', {}, clear=True), \
                    patch('praxis.cutover.active_codex', return_value=[]), \
                    patch('builtins.input', return_value='RESET CODEX'), \
                    patch.object(Path, 'rename', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    apply(layout, path)
            archive = next(layout.state.glob('cutover-backup-*'))
            journal = read_json(archive / 'moves.json')
            self.assertEqual(journal[0]['source'], str(layout.codex))
            self.assertFalse(journal[0]['completed'])
            self.assertTrue((archive / 'recovery-required.json').exists())

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'state.json'
            atomic(p, '{"x":1}')
            self.assertEqual(read_json(p), {'x': 1})
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_unsafe_archives_rejected(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('symlink', tarfile.SYMTYPE), ('fifo', tarfile.FIFOTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / 'a.tar'
                with tarfile.open(archive, 'w') as tar:
                    entry = tarfile.TarInfo(name); entry.type = kind
                    tar.addfile(entry)
                with self.assertRaises(PraxisError):
                    unpack(archive, Path(tmp) / 'output')

    def test_safe_source_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'a.tar'
            with tarfile.open(archive, 'w') as tar:
                entry = tarfile.TarInfo('root/file'); entry.size = 3
                tar.addfile(entry, io.BytesIO(b'abc'))
            unpack(archive, Path(tmp) / 'output', True)
            self.assertEqual((Path(tmp) / 'output/file').read_text(), 'abc')

    def test_existing_config_is_never_implicitly_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp); config = layout.codex / 'config.toml'
            atomic(config, 'model="existing"')
            with patch('praxis.install.install_component') as install:
                with self.assertRaises(PraxisError):
                    bootstrap(layout, authenticate=False)
                install.assert_not_called()
            self.assertEqual(config.read_text(), 'model="existing"')

    def test_doctor_missing_install_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(doctor(Layout(tmp))['ready'])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_configuration_has_single_workflow_and_advisory_memory(self):
        import tomllib
        with tempfile.TemporaryDirectory() as tmp:
            config = tomllib.loads(base_config(Layout(tmp)))
            self.assertNotIn('model_instructions_file', config)
            self.assertNotIn('experimental_compact_prompt_file', config)
            self.assertFalse(config['features']['memories'])
            self.assertFalse(config['features']['plugins'])
            self.assertFalse(config['features']['remote_plugin'])
            self.assertFalse(config['features']['apps'])
            self.assertFalse(config['mcp_servers']['engram']['required'])

    def test_routing_no_silent_downgrade_of_review(self):
        route = {'quality': {'model': 'q', 'effort': 'high'}, 'standard': {'model': 's', 'effort': 'medium'},
                 'mechanical': {'model': 'm', 'effort': 'medium'}}
        result = respond({'tool_name': 'collaborationspawn_agent', 'tool_input': {
            'agent_type': 'reviewer', 'fork_turns': 'none', 'model': 'm', 'reasoning_effort': 'low'}}, route)
        args = result['hookSpecificOutput']['updatedInput']
        self.assertEqual((args['model'], args['reasoning_effort']), ('q', 'high'))
        result = respond({'tool_name': 'spawn_agent', 'tool_input': {'fork_turns': 'all', 'model': 'm'}}, route)
        self.assertNotIn('model', result['hookSpecificOutput']['updatedInput'])

    def test_runtime_infrastructure_error_even_with_cli_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'log'
            log.write_text(json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution', 'status': 'failed', 'exit_code': 1,
                'aggregated_output': 'error building bubblewrap command: cannot establish app-server socket mount isolation'}}))
            self.assertEqual(len(infrastructure_errors(log)), 1)
            log.write_text(json.dumps({'type': 'error', 'message': 'You’ve hit your usage limit'}, ensure_ascii=False))
            self.assertEqual(len(infrastructure_errors(log)), 1)

    def test_cutover_refuses_active_codex(self):
        with tempfile.TemporaryDirectory() as tmp, patch('praxis.cutover.active_codex', return_value=[123]), patch('os.isatty', return_value=True):
            with self.assertRaisesRegex(PraxisError, 'standalone terminal'):
                apply(Layout(tmp), 'not-read.json')

    def test_inventory_does_not_expose_auth_or_shell_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atomic(root / 'auth.json', '{"secret":"never-report"}')
            self.assertEqual(fingerprint(root)['configuration_sha256'], {})
            atomic(root / '.bashrc', 'export CODEX_HOME="sensitive-path"')
            self.assertNotIn('sensitive-path', json.dumps(shell_conflicts(root)))


if __name__ == '__main__':
    unittest.main()
