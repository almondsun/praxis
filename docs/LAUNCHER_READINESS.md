# Codex launcher ownership and release promotion

The October 4 workstation audit found this chain: Mise's
`installs/codex/latest/bin/codex` precedes its `shims/codex` and `~/.local/bin/codex`.
The latter is itself a script invoking `mise use`/`mise x`; global
`~/.config/mise/config.toml` requests `codex = "latest"`. The installed Mise binary
currently reports 0.159.2, but this does not establish durable Praxis ownership.
Praxis reset previously archived only the local launcher. Inventory, reset,
bootstrap and doctor now check this competing resolution without invoking it.
No workstation configuration is automatically rewritten or included in reset's
move scope. Configuration remediation needs its own reviewed backup and approval.
Discovery includes global, system and ancestor project Mise TOML layouts,
environment variants, grouped `conf.d`, `.tool-versions`, backend-qualified tool
names and Mise shell aliases. Custom discovery filename overrides are blockers.
Conventional shell startup/alias files, Fish autoload and redirected XDG/ZDOTDIR
locations are inspected without executing shell code. Arbitrary dynamically
sourced code still requires the fresh standalone-shell inspection below.

The cutover change alters installation-bound source hashes, requiring isolated
reprovisioning and a fresh complete self-test. It does not change component pins,
model routing, engineering policy, Engram initialization or Taskbox. The accepted
Taskbox candidate and its pilot gates remain immutable and do not need repetition.

Remaining sequence, with explicit authorization before promotion or destruction:

1. Complete focused review, unit/platform CI and hash-bound isolated validation
   on the final source. Keep `approved: false` throughout development.
2. Obtain authorization for release promotion. Change only the approval field,
   commit/publish the release and run CI. This changes the exact lock hash even
   though component pins stay identical. Reprovision the isolated installation
   and run the self-test bound to that new lock/installation hash; never transfer
   or relabel the old readiness result. Do not repeat Taskbox.
3. Obtain explicit authorization for the workstation's narrowly reviewed launcher
   remediation. Back up affected Mise configuration and Codex-specific launcher
   ownership separately; preserve unrelated tool configuration. Resolve blockers
   and inspect ordinary resolution in a fresh standalone terminal.
4. With all Codex sessions/processes closed, generate and review a new inventory
   from that terminal. Review exact reset targets, services, launcher evidence,
   credentials handling, backup destination and rollback instructions. The apply
   operation creates the private move archive immediately before destructive
   work; no rollback archive exists merely because inventory was generated.
5. After explicit cutover authorization, apply that unchanged inventory using
   `RESET CODEX`, then run production `sh bootstrap`. Production paths, auth and
   hook trust differ from isolated validation. Use native hook consent, run the
   production self-test, and run `doctor --runtime` from the ordinary shell.
   Verify `type -a codex`, clear any old shell command cache, and confirm the
   installed launcher resolves to the locked Praxis executable.
6. If production validation fails, preserve diagnostics and leave readiness
   false. Inspect move/service journals; close Codex and move new paths aside
   before explicitly restoring Agentcore and separately backed-up tool-manager
   state. Restoration is manual, never an automatic fallback.

Approval-field promotion is metadata, but it still invalidates byte-bound
readiness. No action above is performed merely by writing this procedure.
With the current lockfile formatting, the approval-only edit would change SHA-256
from `9a7a0b53805741504439a55bd30c257eb2279e31b0070ca1d68b63795e4822bc`
to `f8bb5534eb70cf7108fe402898684d43cced14b85e550c5b4a1863708bf938dc`.
Recompute it from the actual promoted file; this calculation is not approval.
