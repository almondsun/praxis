# Development evidence

Updated 2026-10-01. Agentcore remains the active environment; production cutover
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
  memory-independent review role configuration and native consent preservation
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
its final report. Review roles now disable Engram and explicitly require complete
final delivery without memory bookkeeping. Model tiers and review criteria are
unchanged. Pinned Codex source also confirms that native child permissions inherit
the parent's live sandbox; read-only role defaults are not an enforced boundary.
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
Fresh self-test `1790886761414324090` is running with these corrections.

Earlier integration attempts preserved keyring authentication, native trust
normalization and remote-plugin activation issues. File-backed isolated login
and native skill discovery resolved those issues without touching active
Agentcore or changing pinned upstream sources. Focused implementation and
security rereviews found no remaining blocking findings in the reviewed fixes.

The earlier passed smoke remains evidence of that installation, not readiness
for a subsequently changed installation manifest. Readiness is hash-bound.

## Limits and remaining deployment work

Arch and Ubuntu 24.04 container CI passed on source commit `9e04612`:
[run 36880605579](https://github.com/almondsun/praxis/actions/runs/36880605579).
Each job ran the unit suite and two isolated provision-only installations with
empty error lists. CI does not authenticate or run live model, desktop, hook-trust
or recovery tests; those platform-specific behaviors remain unverified there.
The dependency lock remains `approved: false` pending the current live integration
gate. The user selected a new `/home/mitin/code/praxis-pilot` taskbox CLI project
for the real pilot, pending that gate. No pilot implementation or cutover has
occurred. The pilot must use native hook trust without the fixture bypass, retain
actual model/skill/TDD/memory/recovery/review evidence, and finish locally. The
user explicitly excluded production cutover from the pilot task.
Production hook trust must be granted through Codex's native `/hooks` interface;
the controlled fixture trust bypass is not used for ordinary production resume.
