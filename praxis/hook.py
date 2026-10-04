"""Small activation/routing adapter; no engineering workflow implementation."""
import json
import os
from pathlib import Path
import runpy
import sys

if __package__:
    from .project import prepare_project
else:
    # Load the managed source directly; neither create nor consume a helper pycache.
    prepare_project = runpy.run_path(str(Path(__file__).with_name('project.py')))['prepare_project']


def respond(event, routing, project=None):
    if event.get('hook_event_name') == 'SessionStart':
        return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext':
            'Praxis: invoke the installed using-superpowers skill before engineering work. '
            'Superpowers owns the workflow. Git/checkpoint is authoritative; Engram is advisory. '
            'Read PRAXIS_CHECKPOINT.md when present; do not infer completion from chat memory. '
            'Resolved project: ' + json.dumps(project) + '. Routing tiers: ' + json.dumps(routing)}}
    name = event.get('tool_name', '')
    if not name.endswith(('spawn_agent', 'fork_agent')):
        return {}
    args = event.get('tool_input', {})
    if not isinstance(args, dict):
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                      'permissionDecisionReason': 'Invalid delegation arguments'}}
    args = dict(args)
    if args.get('fork_turns', 'all') == 'all':
        # Full-history sessions inherit a known main tier. Do not add forbidden overrides.
        args.pop('model', None); args.pop('reasoning_effort', None)
    else:
        role = args.get('agent_type', '')
        tier = ('quality' if role in ('reviewer', 'security-auditor', 'interop-auditor') else
                'mechanical' if role == 'mechanical' else 'standard')
        requested = next((value for value in routing.values() if value['model'] == args.get('model')), None)
        chosen = routing[tier] if role in ('reviewer', 'security-auditor', 'interop-auditor', 'mechanical') else requested or routing[tier]
        args.update(model=chosen['model'], reasoning_effort=chosen['effort'])
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow', 'updatedInput': args}}


if __name__ == '__main__':
    try:
        event = json.load(sys.stdin)
        routing = json.loads(Path(__file__).with_name('routing.json').read_text())
        project = None
        if event.get('hook_event_name') == 'SessionStart' and \
                os.environ.get('PRAXIS_PROJECT_ENTRY_MODE') != 'read-only-review':
            configuration = json.loads(Path(__file__).with_name('project.json').read_text())
            project = prepare_project(event['cwd'], **configuration)
        print(json.dumps(respond(event, routing, project)))
    except Exception as error:
        if 'event' in locals() and event.get('hook_event_name') == 'SessionStart':
            # Exit 2 alone only reports a hook failure. Native continue:false stops startup.
            print(json.dumps({'continue': False, 'stopReason': 'Praxis project entry blocked: ' + str(error)}))
        else:
            print('Praxis hook failed: ' + str(error), file=sys.stderr)
            sys.exit(2)
