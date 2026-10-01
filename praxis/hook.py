"""Small activation/routing adapter; no engineering workflow implementation."""
import json
from pathlib import Path
import sys


def respond(event, routing):
    if event.get('hook_event_name') == 'SessionStart':
        return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext':
            'Praxis: invoke the installed using-superpowers skill before engineering work. '
            'Superpowers owns the workflow. Git/checkpoint is authoritative; Engram is advisory. '
            'Read PRAXIS_CHECKPOINT.md when present; do not infer completion from chat memory. '
            'Routing tiers: ' + json.dumps(routing)}}
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
        print(json.dumps(respond(event, routing)))
    except Exception as error:
        print('Praxis hook failed: ' + str(error), file=sys.stderr)
        sys.exit(2)
