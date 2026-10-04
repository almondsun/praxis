"""Small integration exercise, not an engineering benchmark or ranking."""
import json
import re
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from .core import ROOT, Layout, PraxisError, atomic, read_json, run, sha, tree_hashes, write_json
from .session import execute


def sandbox_check(project, args, *, expect_failure=False):
    """No network or host home; only runtime libraries and immutable fixture."""
    command = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session',
               '--ro-bind', '/usr', '/usr']
    for name in ('/lib', '/lib64', '/bin'):
        if Path(name).exists():
            command += ['--ro-bind', name, name]
    command += ['--tmpfs', '/tmp', '--proc', '/proc', '--dev', '/dev',
                '--ro-bind', str(project), '/submission', '--chdir', '/submission',
                '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
                '--setenv', 'HOME', '/tmp', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', *args]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    output = f'Exit code: {completed.returncode}\n' + completed.stdout + completed.stderr
    if (expect_failure and completed.returncode == 0) or (not expect_failure and completed.returncode != 0):
        raise PraxisError('Independent sandbox validation returned unexpected status: ' + output[-2000:])
    return output


def require_regression_evidence(output, *, red=False):
    count = re.search(r'\bRan ([1-9][0-9]*) tests?\b', output)
    outcome = re.search(r'FAILED \([^\n]*failures=[1-9][0-9]*', output) if red else re.search(r'^OK\s*$', output, re.MULTILINE)
    if not count or not outcome:
        raise PraxisError(('Nonempty failing baseline tests' if red else 'Nonempty passing regression tests') + ' not demonstrated')

ACCEPTANCE = '''import total
assert total.total([]) == 0
assert total.total([1, -2, 5]) == 4
assert total.total(iter([2, 3])) == 5
assert total.total([10**80, 1]) == 10**80 + 1
for value in ([True], [1.5], ['1'], [1, False]):
    try: total.total(value)
    except TypeError: pass
    else: raise AssertionError('Invalid value accepted: ' + repr(value))
print('Independent acceptance passed')
'''


def runtime_evidence(layout, destination):
    routing = read_json(ROOT / 'config/routing.json')
    allowed = {(x['model'], x['effort']) for x in routing.values()}
    records = []
    sessions = layout.codex / 'sessions'
    for path in sessions.rglob('*.jsonl') if sessions.exists() else []:
        meta = {}
        skills = []
        contexts = []
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('type') == 'session_meta':
                meta = row['payload']
            elif row.get('type') == 'turn_context':
                contexts.append(row['payload'])
            elif row.get('type') == 'response_item' and row.get('payload', {}).get('role') == 'developer':
                value = json.dumps(row['payload'])
                if 'Available skills' in value:
                    skills.append(value)
        main = meta.get('source') == 'exec'
        role = meta.get('agent_role')
        tier = ('quality' if main or role in ('reviewer', 'security-auditor', 'interop-auditor') else
                'mechanical' if role == 'mechanical' else 'standard' if role == 'implementer' else None)
        visible = any('using-superpowers' in value for value in skills)
        remote = any('openai-curated-remote' in value for value in skills)
        for p in contexts:
            model = p.get('model'); effort = p.get('effort', p.get('reasoning_effort'))
            records.append({'session': path.name, 'role': role or ('main' if main else 'default'),
                'model': model, 'effort': effort, 'superpowers_visible': visible,
                'remote_plugins_visible': remote, 'expected_tier': tier})
    if sessions.exists():
        shutil.move(str(sessions), destination / 'sessions')
    write_json(destination / 'runtime-models.json', records)
    if not records or any((r['model'], r['effort']) not in allowed for r in records):
        raise PraxisError('Missing or conflicting runtime model/effort evidence: ' + str(destination))
    if any(not r['superpowers_visible'] or r['remote_plugins_visible'] or
           (r['expected_tier'] and (r['model'], r['effort']) !=
            (routing[r['expected_tier']]['model'], routing[r['expected_tier']]['effort'])) for r in records):
        raise PraxisError('Role routing or native skill isolation not demonstrated: ' + str(destination))
    return records


def selftest(layout):
    from .install import doctor
    check = doctor(layout)
    if check['errors']:
        raise PraxisError(json.dumps(check))
    from .runtime import inspect_runtime
    runtime = inspect_runtime(layout)
    if not runtime['routing_available'] or runtime['ordinary_usage_allowed'] is not True:
        raise PraxisError('Runtime/quota gate unavailable; manually retry later: ' + json.dumps(runtime))
    evidence = layout.state / 'self-tests' / str(time.time_ns()); evidence.mkdir(parents=True)
    # Native automatic Engram initialization uses the Git-root basename.
    identity = 'praxis-selftest-' + uuid.uuid4().hex
    project = evidence / identity; project.mkdir()
    result = {'ready': False, 'evidence': str(evidence), 'lock_sha256': sha(ROOT / 'versions.lock.json'),
              'installation_sha256': sha(layout.codex / 'praxis-install.json')}
    write_json(layout.state / 'readiness.json', result)
    write_json(evidence / 'runtime-admission.json', runtime)
    production = layout
    # Validate the installed configuration, with fresh session/memory runtime state.
    # Never archive or mutate the user's historical session database.
    layout = Layout(evidence / 'session-home')
    layout.data = production.data
    layout.bin = production.bin
    shutil.copytree(production.codex, layout.codex, ignore=shutil.ignore_patterns(
        'auth.json', 'sessions', 'archived_sessions', 'logs', '*.sqlite*', 'shell_snapshots', 'tmp'))
    auth = production.codex / 'auth.json'
    if auth.exists():
        (layout.codex / 'auth.json').symlink_to(auth)
    skills = layout.home / '.agents/skills/superpowers'
    skills.parent.mkdir(parents=True, exist_ok=True)
    skills.symlink_to(layout.component('superpowers') / 'skills', target_is_directory=True)
    # Fresh per-run namespace avoids polluting real project memories.
    def git(*args, cwd=project):
        return run(['git', *args], cwd=cwd, env=layout.fixture_env())
    git('init', '-q', '-b', 'praxis-selftest')
    git('config', 'user.name', 'Praxis self-test')
    git('config', 'user.email', 'selftest@praxis.invalid')
    atomic(project / 'total.py', 'def total(values):\n    return 0\n')
    atomic(project / '.gitignore', '__pycache__/\n.superpowers/\n')
    atomic(project / 'PLAN.md', '# Approved self-test plan\n\nImplement total(iterable): sum integers, reject bool and non-integers with TypeError. '
           'Use Superpowers TDD, isolated delegation and review. Save a durable checkpoint before final verification. '
           'Final verification and closure occur in a fresh recovery session. Local commits authorized; no external actions.\n')
    git('add', '.'); git('commit', '-qm', 'Self-test baseline')
    baseline = git('rev-parse', 'HEAD').strip()
    before_plan = sha(project / 'PLAN.md')
    marker = project / 'PRAXIS_CHECKPOINT.md'

    def checkpoint_committed():
        if not marker.exists() or 'SELFTEST_CHECKPOINT' not in marker.read_text():
            return False
        return git('status', '--porcelain', '--', 'PRAXIS_CHECKPOINT.md').strip() == '' and bool(
            git('ls-files', '--', 'PRAXIS_CHECKPOINT.md').strip())

    try:
        prompt = (f'This controlled integration task is approved. Read PLAN.md and use Superpowers. '
                  f'Use Engram project {identity!r}; save and retrieve the decision that bool is rejected. '
                  'Exercise one isolated standard implementer and one isolated mechanical subagent that only inspects the fixture. '
                  'Write regression tests; prove RED then GREEN. Commit implementation and PRAXIS_CHECKPOINT.md '
                  'containing SELFTEST_CHECKPOINT, the plan, pending final verification, and memory project identity. '
                  'Finish all delegated work before that checkpoint commit. Do NOT perform final verification/closure yet. '
                  'After committing the checkpoint execute sleep 120: the test controller will deliberately interrupt this session. '
                  'Do not ask for routine approvals, change the approved plan, push, or contact external systems other than Engram.')
        first = execute(layout, project, prompt, 'implementation', evidence,
                        interrupt_when=checkpoint_committed, trusted_fixture=True, timeout=900)
        if not first['controlled_interruption'] or not checkpoint_committed():
            raise PraxisError('Controlled checkpoint interruption was not demonstrated')
        first_archive = evidence / 'implementation-runtime'; first_archive.mkdir()
        models = runtime_evidence(layout, first_archive)
        if not {'gpt-6.1-sol', 'gpt-6-luna'} <= {r['model'] for r in models}:
            raise PraxisError('Both delegated routing tiers were not exercised')
        # Prior conversation is removed from active state before the fresh session.
        for pattern in ('state*.sqlite*',):
            for path in layout.codex.glob(pattern):
                shutil.move(str(path), first_archive / path.name)
        execute(layout, project,
                'This is the authorized fresh recovery half of the self-test. Prior conversation is unavailable. '
                'Read Git status/log, PRAXIS_CHECKPOINT.md and PLAN.md. Recover the recorded Engram decision, '
                'complete only pending verification and closure with Superpowers, using the configured native '
                'reviewer role in a fresh context for workflow review, and commit the final checkpoint. '
                'Do not launch a nested Codex CLI from the sandbox. '
                'No external actions. Report the actual tests and review evidence.', 'recovery', evidence,
                trusted_fixture=True, timeout=900)
        recovered_archive = evidence / 'recovery-runtime'; recovered_archive.mkdir()
        recovered = runtime_evidence(layout, recovered_archive)
        if not any(r['role'] == 'reviewer' and r['expected_tier'] == 'quality' for r in recovered):
            raise PraxisError('Configured native quality reviewer was not exercised during recovery')
        if {r['session'] for r in models} & {r['session'] for r in recovered}:
            raise PraxisError('Recovery reused the previous session')
        if sha(project / 'PLAN.md') != before_plan:
            raise PraxisError('Approved fixture plan was modified')
        if git('status', '--porcelain').strip():
            raise PraxisError('Recovery left uncommitted or untracked submission changes')
        output = sandbox_check(project, ['/usr/bin/python3', '-c', ACCEPTANCE])
        atomic(evidence / 'acceptance.log', output)
        native = sandbox_check(project, ['/usr/bin/python3', '-m', 'unittest', 'discover', '-v'])
        require_regression_evidence(native)
        atomic(evidence / 'native-tests.log', native)
        if not list(project.glob('test*.py')):
            raise PraxisError('Fixture regression tests missing')
        red_submission = evidence / 'regression-baseline'
        shutil.copytree(project, red_submission, ignore=shutil.ignore_patterns('.git', '__pycache__', '.superpowers'))
        atomic(red_submission / 'total.py', git('show', baseline + ':total.py'))
        red = sandbox_check(red_submission, ['/usr/bin/python3', '-m', 'unittest', 'discover', '-v'], expect_failure=True)
        require_regression_evidence(red, red=True)
        atomic(evidence / 'baseline-red.log', red)
        # Check real completed MCP events rather than assertions in final messages.
        operations = {}
        memory_results = {}
        for phase in ('implementation', 'recovery'):
            operations[phase] = []
            memory_results[phase] = []
            for line in (evidence / (phase + '.jsonl')).read_text().splitlines():
                item = json.loads(line).get('item', {})
                if (item.get('server') == 'engram' and item.get('status') == 'completed'
                        and not item.get('error') and not (item.get('result') or {}).get('isError')):
                    operations[phase].append(item.get('tool'))
                    if item.get('tool') in ('mem_search', 'mem_context', 'mem_get_observation'):
                        memory_results[phase].append(json.dumps(item.get('result'), ensure_ascii=False).lower())
        if 'mem_save' not in operations['implementation'] or not set(operations['recovery']) & {'mem_search', 'mem_context', 'mem_get_observation'}:
            raise PraxisError('Successful cross-session Engram operations not demonstrated')
        if not any(identity in value and 'bool' in value and 'reject' in value
                   for value in memory_results['recovery']):
            raise PraxisError('Recovery did not retrieve the project-specific bool rejection decision')
        review = evidence / 'review'; review.mkdir()
        submission = review / 'submission'; shutil.copytree(project, submission, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        git('init', '-q', str(review), cwd=review)
        atomic(review / 'changes.diff', git('diff', '--binary', baseline))
        shutil.copy2(evidence / 'acceptance.log', review / 'acceptance.log')
        shutil.copy2(evidence / 'native-tests.log', review / 'native-tests.log')
        shutil.copy2(evidence / 'baseline-red.log', review / 'baseline-red.log')
        schema = evidence / 'review-schema.json'
        write_json(schema, {'type': 'object', 'properties': {'pass': {'type': 'boolean'},
            'blocking_findings': {'type': 'array', 'items': {'type': 'string'}},
            'limitations': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['pass', 'blocking_findings', 'limitations'], 'additionalProperties': False})
        before = tree_hashes(submission)
        execute(layout, review, 'Perform a fresh independent read-only review of submission, changes.diff, '
                'and verification logs. No implementation conversation is available. Check the PLAN.md contract, '
                'tests and checkpoint closure; report any blocking correctness, security or contract issues. '
                'Do not use Engram, modify evidence, or assume success from logs alone. Return the required JSON.',
                'review', evidence, readonly=True, schema=schema, trusted_fixture=True, timeout=900)
        verdict = read_json(evidence / 'review-final.txt')
        if tree_hashes(submission) != before or verdict['blocking_findings'] or verdict['pass'] is not True:
            raise PraxisError('Independent quality review did not pass')
        reviewer_archive = evidence / 'review-runtime'; reviewer_archive.mkdir()
        runtime_evidence(layout, reviewer_archive)
        result.update(ready=True, review=verdict, engram_operations=operations,
                      controlled_interruption=True, recovery='fresh session',
                      note='Integration evidence only; not a guarantee of real-project reliability')
    except Exception as error:
        result.update(error=str(error), repair='Inspect preserved evidence, repair the integration, then manually rerun self-test. No automatic retry or rollback.')
        write_json(evidence / 'result.json', result); write_json(production.state / 'readiness.json', result)
        raise PraxisError(str(error)) from error
    write_json(evidence / 'result.json', result); write_json(production.state / 'readiness.json', result)
    return result
