import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from praxis.core import ROOT
from praxis.project import ProjectError, canonical, git, prepare_project, protect


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'project'
        self.root.mkdir()
        self.engram = self.base / 'pinned-engram'
        self.env = {**os.environ}
        self.env.pop('ENGRAM_PROJECT', None)
        self.calls = []
        real_run = subprocess.run
        def run(command, **kwargs):
            if command[0] != str(self.engram):
                return real_run(command, **kwargs)
            self.calls.append((command, kwargs))
            root = Path(kwargs['cwd'])
            if command[1] == 'init':
                self.assertNotIn('--force', command)
                path = root / '.engram/config.json'
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps({'project_name': root.name}))
                return subprocess.CompletedProcess(command, 0, '', '')
            self.assertEqual(command[1:], ['mcp', '--tools=agent'])
            if (root / '.engram/config.json').exists():
                name = canonical(json.loads((root / '.engram/config.json').read_text())['project_name'])
            else:
                name = 'project'
            identity = {'project': name, 'project_path': str(root), 'project_source': 'config'}
            response = {'jsonrpc': '2.0', 'id': 2, 'result': {'content': [{'type': 'text', 'text': json.dumps(identity)}]}}
            return subprocess.CompletedProcess(command, 0, json.dumps(response) + '\n', '')
        self.mock = patch('praxis.project.subprocess.run', side_effect=run)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def repo(self):
        git(self.root, '-c', 'init.templateDir=', 'init', '-q', env=self.env)

    def binding(self, text='{"project_name":"project"}'):
        path = self.root / '.engram/config.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
        return path

    def prepare(self, path=None, **kwargs):
        return prepare_project(path or self.root, engram=self.engram, env=self.env, **kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_initialized_project_is_not_mutated(self):
        self.repo(); self.binding()
        before = self.snapshot()
        result = self.prepare()
        self.assertFalse(result['git_created'])
        self.assertFalse(result['engram_initialized'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([c[0][1] for c in self.calls], ['mcp'])

    def test_existing_repo_missing_binding_initializes_once_and_is_idempotent(self):
        self.repo()
        first = self.prepare()
        before = self.snapshot()
        second = self.prepare()
        self.assertTrue(first['engram_initialized'])
        self.assertFalse(second['engram_initialized'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([c[0][1] for c in self.calls], ['init', 'mcp', 'mcp'])
        self.assertNotIn('refs/heads', git(self.root, 'show-ref', env=self.env, check=False).stdout)

    def test_subdirectory_uses_root_and_never_creates_nested_repository(self):
        self.repo()
        child = self.root / 'src/deep'; child.mkdir(parents=True)
        result = self.prepare(child, greenfield=True)
        self.assertEqual(result['root'], str(self.root))
        self.assertFalse(result['git_created'])
        self.assertTrue((self.root / '.engram/config.json').is_file())
        self.assertFalse((child / '.git').exists())
        self.assertFalse((child / '.engram').exists())

    def test_malformed_binding_and_symlinks_fail_without_repair(self):
        self.repo()
        for content in ('{', '{}', '{"project_name":""}', '{"project_name":"a/b"}',
                        '{"project_name":"a","project_name":"b"}'):
            with self.subTest(content=content):
                path = self.binding(content)
                before = self.snapshot()
                with self.assertRaises(ProjectError): self.prepare()
                self.assertEqual(self.snapshot(), before)
        path.unlink(); path.symlink_to(self.base / 'missing')
        with self.assertRaises(ProjectError): self.prepare()
        self.assertTrue(path.is_symlink())
        self.assertEqual(self.calls, [])

    def test_subproject_and_private_identity_conflicts_are_not_overwritten(self):
        self.repo(); self.binding()
        child = self.root / 'src'; (child / '.engram').mkdir(parents=True)
        (child / '.engram/config.json').write_text('{"project_name":"other"}')
        with self.assertRaisesRegex(ProjectError, 'Subproject'): self.prepare(child)
        private = self.root / '.git/engram-project-identity.json'
        private.write_text(json.dumps({'version': 1, 'id': 'a' * 32, 'project': 'other'}))
        before = self.snapshot()
        with self.assertRaisesRegex(ProjectError, 'Conflicting'): self.prepare()
        self.assertEqual(self.snapshot(), before)

    def test_private_upstream_identity_is_valid_existing_binding(self):
        self.repo()
        (self.root / '.git/engram-project-identity.json').write_text(json.dumps(
            {'version': 1, 'id': 'a' * 32, 'project': 'project'}))
        before = self.snapshot()
        self.assertFalse(self.prepare()['engram_initialized'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([c[0][1] for c in self.calls], ['mcp'])

    def test_explicit_pristine_greenfield_initializes_both_without_committing(self):
        result = self.prepare(greenfield=True)
        self.assertTrue(result['git_created']); self.assertTrue(result['engram_initialized'])
        self.assertTrue((self.root / '.git').is_dir())
        self.assertTrue((self.root / '.engram/config.json').is_file())
        self.assertNotEqual(git(self.root, 'rev-parse', '--verify', 'HEAD', env=self.env, check=False).returncode, 0)

    def test_arbitrary_non_git_directory_has_one_confirmation_gate_and_no_mutation(self):
        (self.root / 'user.txt').write_text('preserve')
        before = self.snapshot()
        with self.assertRaisesRegex(ProjectError, 'Confirm the intended greenfield root'): self.prepare()
        self.assertEqual(self.snapshot(), before)
        with self.assertRaisesRegex(ProjectError, 'pristine'): self.prepare(greenfield=True)
        self.assertFalse((self.root / '.git').exists()); self.assertEqual(self.calls, [])

    def test_protected_roots_are_never_auto_initialized(self):
        for path, protected in ((self.root, [self.root]), (ROOT, [ROOT]),
                                (Path('/'), []), (Path.home(), [])):
            with self.subTest(path=path):
                # CI checkout ownership may stop Git discovery before the protected-root gate.
                with self.assertRaises(ProjectError):
                    self.prepare(path, greenfield=True, protected_roots=protected)
                with self.assertRaisesRegex(ProjectError, 'Protected'):
                    protect(path.resolve(), protected, True)
        self.assertFalse((self.root / '.git').exists()); self.assertEqual(self.calls, [])

    def test_identity_mismatch_and_native_failures_are_blockers(self):
        self.repo(); self.binding()
        with patch('praxis.project.current_identity', return_value={'project': 'other', 'project_path': str(self.root)}):
            with self.assertRaisesRegex(ProjectError, 'does not match'): self.prepare()
        with patch('praxis.project.current_identity', side_effect=ProjectError('native verification failed')):
            with self.assertRaisesRegex(ProjectError, 'native verification failed'): self.prepare()

    def test_no_git_redirect_or_registered_session_or_fake_memory_is_used(self):
        self.env['GIT_DIR'] = str(self.base / 'unrelated')
        self.env['ENGRAM_CLOUD_AUTOSYNC'] = '1'
        self.env['ENGRAM_CLOUD_TOKEN'] = 'private-token'
        self.env['ENGRAM_DATA_DIR'] = str(self.base / 'unrelated-store')
        self.prepare(greenfield=True)
        self.assertTrue((self.root / '.git').is_dir()); self.assertFalse((self.base / 'unrelated').exists())
        requests = [json.loads(line) for _, kwargs in self.calls if 'input' in kwargs
                    for line in kwargs['input'].splitlines()]
        tools = [r['params']['name'] for r in requests if r['method'] == 'tools/call']
        self.assertEqual(tools, ['mem_current_project'])
        for _, kwargs in self.calls:
            self.assertFalse(any(key.startswith(('GIT_', 'ENGRAM_')) for key in kwargs['env']))

    def test_project_override_is_an_explicit_conflict(self):
        self.env['ENGRAM_PROJECT'] = 'other'
        with self.assertRaisesRegex(ProjectError, 'ENGRAM_PROJECT conflicts'):
            self.prepare(greenfield=True)
        self.assertFalse((self.root / '.git').exists())
        self.assertEqual(self.calls, [])

    def test_option_like_prompt_is_delimited_from_codex_options(self):
        from praxis.core import Layout
        from praxis.session import execute
        from unittest.mock import MagicMock
        layout = Layout(self.base / 'home')
        process = MagicMock()
        process.poll.return_value = 0
        process.wait.return_value = 0
        prompt = '--dangerously-bypass-approvals-and-sandbox'
        with patch('praxis.install.doctor', return_value={'errors': []}), \
                patch('praxis.session.subprocess.Popen', return_value=process) as popen:
            execute(layout, self.root, prompt, 'review', self.base / 'evidence', readonly=True)
        self.assertEqual(popen.call_args.args[0][-2:], ['--', prompt])

    def test_native_hook_returns_real_stop_and_readonly_review_never_initializes(self):
        package = self.base / 'hooks'; package.mkdir()
        for name in ('hook.py', 'project.py'): shutil.copy2(ROOT / 'praxis' / name, package / name)
        (package / 'routing.json').write_text('{}')
        (package / 'project.json').write_text(json.dumps({'engram': str(self.engram)}))
        event = json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(self.root)})
        env = {k: v for k, v in self.env.items() if k != 'PYTHONDONTWRITEBYTECODE'}
        normal = subprocess.run(['python3', str(package / 'hook.py')], input=event, env=env,
                                capture_output=True, text=True, check=True)
        self.assertFalse(json.loads(normal.stdout)['continue'])
        self.assertIn('Confirm', json.loads(normal.stdout)['stopReason'])
        readonly = subprocess.run(['python3', str(package / 'hook.py')], input=event,
                                 env={**self.env, 'PRAXIS_PROJECT_ENTRY_MODE': 'read-only-review'},
                                 capture_output=True, text=True, check=True)
        self.assertIn('hookSpecificOutput', json.loads(readonly.stdout))
        self.assertFalse((self.root / '.git').exists()); self.assertEqual(self.calls, [])
        self.assertFalse((package / '__pycache__').exists())

    def test_reconfiguration_ignores_unmanaged_hook_runtime_directory(self):
        from praxis.core import Layout
        from praxis.install import configure
        layout = Layout(self.base / 'isolated-home')
        runtime = layout.codex / 'praxis-hooks/__pycache__'
        runtime.mkdir(parents=True)
        (runtime / 'old-runtime.pyc').write_bytes(b'preserve')
        with patch('praxis.install.run'):
            configure(layout)
        manifest = json.loads((layout.codex / 'praxis-install.json').read_text())
        self.assertTrue((runtime / 'old-runtime.pyc').exists())
        self.assertTrue(all('__pycache__' not in name for name in manifest['files']))
