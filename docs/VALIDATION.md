# Validation contract

Unit tests: `python3 -m unittest discover -s tests -v`.

Provision-only installation in a disposable home checks downloads, checksums,
Gentle integration, pinned native skill discovery and repeatability without inference.
Linux CI runs unit/provisioning checks on Ubuntu 24.04 and Arch. CI does not have
production credentials and does not claim a live model test.

The live self-test uses the installed configuration but a disposable project,
fresh runtime/session state and a distinct Engram namespace. It must demonstrate
delegated tiers, regression tests, a committed checkpoint, deliberate process
interruption, fresh recovery with old session history unavailable, memory retrieval,
independent acceptance and read-only final review. Evidence is kept outside Git.
Independent regression validation requires a positive executed-test count and
failure against the original broken baseline, followed by success against the
final submission. This proves regression sensitivity; session logs preserve the
implementation's TDD chronology separately.

An outer CLI exit 0 does not prove tool execution or quality. Runtime errors and
model/effort evidence are inspected. Unknown or absent evidence is not success.
Self-test readiness is bound to the installation manifest and dependency lock.

The self-test is an integration smoke, not a replacement for real-project
engineering validation. It cannot establish multi-day reliability, all security
properties, or universal correctness. Interrupted work beyond the last durable
checkpoint always requires reconciliation.

## Current execution record

See `IMPLEMENTATION_STATUS.md` for checks actually executed during development.
CI definitions are not evidence that either platform job has run.
