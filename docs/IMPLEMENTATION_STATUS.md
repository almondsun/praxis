# Development evidence

Updated 2026-10-02. Agentcore remains the active environment; production cutover
has not been applied.

Executed locally:

- Exact release artifacts installed in the isolated development home; checksum
  and installed-file verification passed.
- Repeated provision-only bootstrap: no configuration errors; correctly reports
  not ready before a successful live self-test.
- Twenty-four unit/regression tests passed, including configuration ownership,
  archive safety, runtime-error classification, role routing, Git environment
  isolation, launcher/hook inventory, active-process recheck and stale services,
  interruption journals, native trust normalization, nonempty regression checks,
  runtime role/skill isolation, production/control deadline separation and
  supported review-role configuration and native consent preservation
  with non-BMP Unicode paths.
- Restricted, network-isolated validation sandbox executed system Python without
  access to the user home.
- Authenticated app-server inspection confirmed all configured model/effort pairs
  and ordinary usage availability.

## Live evidence

Evidence is private and outside Git under the isolated development home at
`/home/mitin/.local/state/praxis-development/home`.

- Native discovery probe `diagnostics/skill-discovery-01` demonstrated the main
  Astra/high session and delegated Sol 6.1/medium and Luna 6/medium sessions.
  Pinned Superpowers skills were visible; account-installed plugin skills were
  absent. Plugin support is disabled, as explicitly approved.
- Self-test `1790826926275175160` passed implementation, committed planned
  interruption, fresh-session recovery, Engram decision retrieval, nine tests,
  independent acceptance and read-only review with no blocking findings.
- The later strengthened self-test `1790828017551031552` stopped during
  implementation on an actual usage limit. It did not reach checkpoint/recovery
  or review and is preserved as infrastructure evidence, not a quality failure.
- Fresh strengthened self-test `1790864069532620139` reached its 900-second
  recovery deadline (`stop_reason: phase_deadline`, CLI termination -15).
  Implementation committed a checkpoint and was deliberately interrupted after
  410.13 seconds with no infrastructure errors. A fresh recovery session retrieved
  the project-specific Engram decision, passed five fixture tests and eleven
  explicit acceptance checks, and dispatched an isolated Astra/high reviewer.
  The final review report and closure commit were still pending at termination.
  This is an incomplete bounded smoke, not a completed quality gate or an actual
  quota-exhaustion event. Current readiness is false; no automatic retry runs.
  The independent baseline-red check, acceptance and outer read-only review were
  not reached. The stronger regression gate therefore remains unproven live.

The timeout diagnosis found that the recovery reviewer reported no findings at
14:31:33 UTC, then continued Engram bookkeeping at 14:35:14 UTC before producing
its final report. Review roles now instruct complete final delivery without memory
bookkeeping. Native child MCP and permission settings inherit the parent; these
instructions are behavior guardrails, not isolation. Model tiers and review
criteria are unchanged.
The separate final reviewer remains a directly enforced read-only invocation.
Self-test `1790866445215471730` recovered its checkpoint, retrieved Engram state,
and passed eight tests and 21 contract checks. Its agent attempted a nested Codex
CLI review from the sandbox; model API connection/routing failed before inspection.
The separate outer reviewer found no blocking code issue but rejected the still
blocked checkpoint/closure. This run did not pass the integration gate. Workflow
guidance now requires the native configured reviewer, not nested CLI execution.

Native hook-consent validation `diagnostics/native-hook-consent-02` used the same
`hooks/list` and `config/batchWrite` mechanism as Codex's `/hooks` interface. Only
the two checksum-verified isolated Praxis hooks were trusted, by exact native
hash; no blanket bypass was used. Doctor reported no errors after consent and
after reconfiguration. Config normalization excludes only valid native consent
records, preserves them on bootstrap, and rejects hook enable/disable edits.
Focused security rereview confirmed the Unicode consent round-trip fix.
Self-test `1790886761414324090` completed checkpoint/recovery, verification and
separate final review, but remained blocked because native `reviewer` dispatch
failed. The server restart interrupted wrapper finalization; authentic reviewer
JSON and phase results were preserved, and its result explicitly records the
integration blocker and unavailable outer CLI exit.

The cause was established from pinned 0.159.2 source: role files parse independently,
so an MCP stanza containing only `enabled=false` has no valid transport and causes
the role to be omitted. Even a full transport would not change the child's MCP
servers: bounded role overrides omit MCP and sandbox fields. Those ineffective
settings were removed. Native workflow review is fresh-context and instructed not
to use memory or edit; the separate final review enforces read-only and disabled
Engram at session level.

Focused live probe `diagnostics/native-review-role-01` passed with normal native
hook consent, no fallback and no blanket bypass. Runtime records showed parent
and configured reviewer both Astra/high, Superpowers visible, remote plugins
absent, and no reviewer Engram invocation. The complete review returned no findings.
The full smoke additionally requires actual configured native reviewer runtime
evidence before passing; a generic fallback cannot satisfy it.
Fresh full self-test `1790887965811629228` stopped on an actual usage limit
after 258.08 seconds, before the planned checkpoint. Its meaningful TDD evidence
(11 assertion failures followed by six passing tests) is preserved; it did not
reach recovery or final review and is not a completed integration gate.
On explicit user continuation, runtime inspection showed all configured tiers
available and ordinary usage allowed, with 97% primary and 37% weekly quota
remaining. Fresh full self-test `1790909044717343313` passed: implementation
checkpoint and deliberate interruption (421.60 seconds), fresh recovery
(405.09 seconds), native Astra/high reviewer, seven unit tests, independent
acceptance, twelve reproduced baseline assertion failures, and separate
read-only review (74.02 seconds) with no blocking findings. Engram write and
fresh project-specific retrieval were verified from tool events. Readiness is
bound to the current installation and lock hashes. The final reviewer could
not independently inspect Git chronology because its immutable submission
copy excludes Git metadata; controller/runtime evidence records that chronology.

Earlier integration attempts preserved keyring authentication, native trust
normalization and remote-plugin activation issues. File-backed isolated login
and native skill discovery resolved those issues without touching active
Agentcore or changing pinned upstream sources. Focused implementation and
security rereviews found no remaining blocking findings in the reviewed fixes.

The earlier passed smoke remains evidence of that installation, not readiness
for a subsequently changed installation manifest. Readiness is hash-bound.

## Limits and remaining deployment work

Arch and Ubuntu 24.04 container CI passed on source commits `9e04612`, `7e98054`
and `9bdfa3a`:
[initial run](https://github.com/almondsun/praxis/actions/runs/36880605579) and
[consent-repair run](https://github.com/almondsun/praxis/actions/runs/36922976277),
and [native-role run](https://github.com/almondsun/praxis/actions/runs/36924971201).
Each job ran the unit suite and two isolated provision-only installations with
empty error lists. CI does not authenticate or run live model, desktop, hook-trust
or recovery tests; those platform-specific behaviors remain unverified there.
The dependency lock remains `approved: false` pending the real pilot and release
decision; no pins were changed. The user selected a new
`/home/mitin/code/praxis-pilot` taskbox CLI project. The repository was initialized
from an empty directory with no copied project files or history, no remote, and
repository-local user identity. Its discovery/design ran through the actual
installed Praxis environment with normal native hook consent. Runtime evidence
confirmed Astra/high, native Superpowers visibility and no remote plugin skills.
The agent read using-superpowers and brainstorming, then stopped: Engram resolved
`praxis-pilot` from Git, but scoped context/search/review-list reads returned
`unknown_project`. It did not initialize/register the project before stopping.
This is an unresolved fresh-project integration path, not proof that Engram
persistence or recovery is broken. The pilot is paused under the user's explicit
stop-on-subsystem-issue rule. CLI exit 0 only means the blocker report completed;
it does not mean discovery or the pilot passed. No design proposal, project files,
implementation, commits, TDD, delegation or recovery have occurred in the pilot.
Raw evidence remains private in `pilot-taskbox-01`; the passed smoke is preserved.
On the user's explicit continuation, exact pinned Engram source and isolated
native MCP probes established the cause. An explicit write to an unbound new
project is rejected; native `engram init` supplies the required local binding.
Scoped reads still report `unknown_project` before the first stored observation.
Probe `diagnostics/engram-empty-project-02` passed native initialization, a real
first configuration-decision write, subsequent scoped reads and retrieval from a
fresh MCP process, without supplied session identity or explicit registration.
No upstream code, pins, installed hooks or model routing changed. The supported
startup path is now documented. Actual pilot discovery retry `discovery-02`
passed native initialization and a genuine configuration-decision save plus
scoped retrieval. Runtime again confirmed Astra/high with pinned Superpowers
visible and no remote plugin skills. The only project file is its newly generated
native `.engram/config.json`; no product scaffolding or implementation was copied
or written. Superpowers produced the concrete taskbox design and stopped at its
required conversational design approval. The user approved that design.
The initial specification phase stopped on an actual usage limit after 892.20
seconds, preserving the draft and checkpoint. On explicit manual continuation,
a fresh session finished self-review, retrieved architecture observation #3,
and committed the four intended documentation/native-binding files as
`0f2a59ab04e07c01fda0e51bd1ec54e94d713dca`, with a clean working tree.
The written specification is now presented for human review; its approval and
the later plan gate remain pending. No product code or tests exist yet.
This quota interruption/fresh documentation recovery does not substitute for
the later required deliberate implementation-checkpoint recovery exercise.
The initial model stop
remains recorded as an intervention,
not an Engram persistence failure or a passed pilot phase.
No pilot implementation or
cutover has occurred. The pilot must use native hook trust without the fixture bypass, retain
actual model/skill/TDD/memory/recovery/review evidence, and finish locally. The
user explicitly excluded production cutover from the pilot task.
Production hook trust must be granted through Codex's native `/hooks` interface;
the controlled fixture trust bypass is not used for ordinary production resume.
