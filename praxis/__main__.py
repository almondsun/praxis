import argparse
import json
import sys

from .core import Layout, PraxisError


def main():
    parser = argparse.ArgumentParser(description='Praxis: reproducible Codex production configuration')
    parser.add_argument('--home', help='Explicit isolated test/install home; defaults to current user')
    commands = parser.add_subparsers(dest='command', required=True)
    bootstrap = commands.add_parser('bootstrap')
    bootstrap.add_argument('--no-auth', action='store_true', help='Provision only; never declares ready')
    bootstrap.add_argument('--no-self-test', action='store_true', help='Provision only; never declares ready')
    doctor = commands.add_parser('doctor')
    doctor.add_argument('--runtime', action='store_true', help='Also inspect available models/quota without inference')
    commands.add_parser('self-test')
    resume = commands.add_parser('resume')
    resume.add_argument('project')
    commands.add_parser('update')
    cutover = commands.add_parser('cutover')
    cutover.add_argument('--apply', help='Apply the exact reviewed inventory JSON path from a terminal')
    args = parser.parse_args()
    layout = Layout(args.home)
    try:
        if args.command == 'bootstrap':
            from .install import bootstrap, doctor
            bootstrap(layout, authenticate=not args.no_auth)
            result = doctor(layout)
            if result['errors']:
                raise PraxisError(json.dumps(result))
            if not args.no_self_test and not args.no_auth:
                from .selftest import selftest
                result = selftest(layout)
            else:
                result['ready'] = False
                result['reason'] = 'Provisioned; authenticated live self-test still required'
        elif args.command == 'doctor':
            from .install import doctor
            result = doctor(layout)
            if args.runtime:
                from .runtime import inspect_runtime
                result['runtime'] = inspect_runtime(layout)
        elif args.command == 'self-test':
            from .selftest import selftest
            result = selftest(layout)
        elif args.command == 'resume':
            from .session import resume
            result = resume(layout, args.project)
        elif args.command == 'update':
            from .maintenance import check_updates
            result = check_updates(layout)
        else:
            from .cutover import inventory, apply
            result = apply(layout, args.apply) if args.apply else inventory(layout)
        print(json.dumps(result, indent=2))
        return 0 if result.get('ready', True) else 1
    except (PraxisError, OSError, ValueError) as error:
        print('Praxis: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
