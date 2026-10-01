# Praxis

Reproducible Linux Codex setup: **Gentle infrastructure + Superpowers workflow +
Engram advisory memory + Git-authoritative recovery**.

Praxis is independent of Agentcore. It owns installation, compatibility checks,
policy and validation, not a second planning or engineering framework.

## Install on a fresh machine

Supported target: Arch Linux or Ubuntu 24.04 LTS, x86-64. Git must be available
to clone the repository. From the clone:

```sh
sh bootstrap
```

Bootstrap requests host authorization only for missing prerequisites, installs
exact release artifacts from `versions.lock.json`, configures Codex through Gentle,
exposes the pinned Superpowers source release through native Codex skill discovery, requests
Codex login if needed, then executes the live integration self-test.
Credentials use Codex's supported file-backed store in the private Codex home;
fresh self-test sessions reference that credential file without copying it into
the repository or publishing it. Independent fixture checks run in a restricted
Bubblewrap sandbox with no network or access to the user home.

Launch the installed executable explicitly:

```sh
~/.local/bin/codex
```

The standard Codex `/hooks` interface must trust Praxis's installed hooks before
interactive use. Production resume uses normal native trust checks, including
project-local hooks. Only disposable self-test fixtures bypass hook trust after
checking installed code. Hook controls are guardrails; live runtime evidence is
also required. Installing skills alone does not grant hook trust.

An existing customized Codex installation is never silently overwritten.
For this workstation, follow [clean cutover](docs/CUTOVER.md) first.

## Commands

Run from the repository:

```sh
python3 -m praxis doctor
python3 -m praxis doctor --runtime
python3 -m praxis self-test
python3 -m praxis resume /absolute/project/path
python3 -m praxis update
python3 -m praxis cutover
```

`doctor --runtime` reads model availability and account quota without inference.
`self-test` consumes a small amount of inference quota. `resume` is an explicit
user-authorized invocation, not a daemon. Production resume has no fixed deadline;
the smoke test bounds its own phases. Neither command waits for a quota reset or
automatically starts another attempt. A failed self-test leaves the new setup
installed and **not ready**; diagnostics remain under `~/.local/state/praxis`.

For installation testing without sign-in or inference:

```sh
python3 -m praxis --home /absolute/disposable/home bootstrap --no-auth --no-self-test
```

Provision-only returns exit 1 and `ready: false` until a live self-test passes.
Never use a temporary test home as your production configuration.

## Component ownership

| Concern | Owner |
|---|---|
| Execution, sessions, sandbox | Codex |
| Selected infrastructure provisioning | Gentle-AI custom Engram-only installation |
| Engineering workflow | Superpowers |
| Searchable advisory memory | Engram, machine-local |
| Approved plan, code and recovery checkpoint | Project Git repository |
| Pinning, compatibility overlay, self-test | Praxis |
| Resume timing and weekly upgrades | You |

Gentle's default presets are deliberately not used. Its Codex Engram adapter
also generates base-instruction replacements, custom compaction configuration and
SDD profiles. Praxis deactivates those overlaps after provisioning, keeps upstream
memory guidance additive, and configures explicit role routing. Run configuration
maintenance through Praxis; direct `gentle-ai sync` may reintroduce overlaps and
will be detected as configuration drift.

Superpowers skills are discovered through a symlink to the exact pinned upstream
source release. Praxis supplies one small activation hook; upstream files remain
unchanged. Plugin support is disabled: in Codex 0.159.2, disabling the remote
catalog alone still synchronizes account-installed plugins. Native skill discovery
avoids that competing activation path without changing your account. No upstream
source is forked or patched.

Engram's setup helper is disabled during Gentle installation because its default
Codex plugin path follows `main`. Praxis uses the pinned Engram binary over MCP
and additive upstream memory instructions. No cloud/Git memory sync is enabled.

## Engineering and recovery

After scope/design approval, Superpowers performs implementation, TDD, debugging,
review and verification. Routine local work does not need repeated consent.
External mutations and material decisions still require authorization. Completion
requires fresh checks and review with no unresolved blocking correctness,
security, compatibility or contract findings.

At meaningful milestones the agent writes and commits `PRAXIS_CHECKPOINT.md`,
referencing the Superpowers plan/ledger, last verified code, remaining work,
evidence and next action. Git beats memory. Abrupt termination may leave changes
since the last checkpoint; recovery inspects and reconciles them. Manual resume
starts a fresh session; it does not require the old conversation.

The first model tiers are Astra/high for planning, high-risk work and final review;
Sol 6.1/medium for ordinary engineering; Luna 6/medium for fully specified mechanical
work. Routing is centralized in `config/routing.json`, with no silent downgrade.

## Validation and maintenance

```sh
python3 -m unittest discover -s tests -v
```

See [validation](docs/VALIDATION.md) and [weekly maintenance](docs/MAINTENANCE.md).
Configuration, version pins and tests belong in Git. Credentials, installed
artifacts, memory, session logs and disposable self-test projects do not.
