# Clean cutover from Agentcore

Agentcore stays active during development. Do not dismantle the environment from
inside the Codex session doing the work. A standalone terminal must perform the
final cutover with all Codex processes closed.

1. Finish installation/integration development. Read `VALIDATION.md`; do not
   describe unexecuted platform or live tests as passing.
2. Generate an inventory: `python3 -m praxis cutover`. Review the returned file.
   It covers user Codex configuration/state, custom skill roots, Gentle/GGA
   configuration, existing Codex/Gentle/Engram launchers, relevant user services
   and shell override locations.
   Inventory schema 2 additionally records the terminal PATH, every executable
   `codex` on it, and inspected global/project Mise configuration hashes. Older
   inventories must be regenerated. Competing executables (including lower-priority
   fallbacks), Mise Codex ownership at any version, a missing Praxis launcher PATH
   entry, and shell aliases/functions are blockers. Neither inventory nor reset
   executes competing launchers or rewrites tool-manager configuration.
3. Resolve listed blockers explicitly. Shell startup functions/aliases are not
   mechanically rewritten. System policy is never removed. Inspect the target
   project for local `.codex`, `AGENTS.md`, skills or plugins that could reactivate
   retired workflows; do not recursively delete unrelated repositories.
   Resolve launcher ownership explicitly before reset. For Mise, review and back
   up the affected configuration, remove only the Codex tool entry using a separately
   authorized remediation, and remove/disable only its competing Codex shims and
   installed launcher paths. Preserve unrelated tools. Start a fresh standalone
   shell, clear command hashing (`hash -r` in Bash), and inspect `type -a codex`.
   Do not solve this by placing Praxis ahead of an otherwise active `latest` tool:
   fallback launchers and future tool-manager activation still compete.
4. Close Codex, including daemon/background processes. In a standalone terminal:

   ```sh
   cd /path/to/praxis
   python3 -m praxis cutover --apply /absolute/path/to/reviewed-inventory.json
   sh bootstrap
   ```

   The first command requires the exact confirmation `RESET CODEX`. It rejects
   changed inventory and active Codex processes. Existing configuration and
   historical runtime data are archived under a private timestamped directory.
   Authentication stays local; it is not printed, exported or committed. Known
   inventoried automation is disabled. No unrelated project code is deleted.
   Launcher ownership and its inventory snapshot are checked again before
   confirmation and under the reset lock, before any service is stopped or file
   is moved. Regenerate inventory after any PATH/configuration remediation.
5. Bootstrap activates only Praxis. The self-test runs immediately afterward. A
   failure leaves Praxis installed, with diagnostics and `ready: false`.
   Bootstrap preflights launcher ownership before downloads. Doctor checks both
   the installed launcher symlink and ordinary PATH resolution against the exact
   pinned binary, as well as competing executable/configuration ownership. Run
   doctor from the real standalone shell, not a PATH sanitized just for the test.
   Inspect local tool-manager and shell overrides again when entering a new
   project; this is detection, not a guarantee against future user edits.

The archive contains `inventory.json`, service-state journals, incremental
`moves.json` and either clean
baseline evidence or `recovery-required.json`. Do not blindly restore over newly
created files: inspect moves and rename the new setup aside before any explicit
restoration. Restoration is manual; Agentcore is never automatically reactivated.

The reset command and bootstrap are deliberately separate: an ordinary fresh
installation must not imply permission to erase existing customizations.
