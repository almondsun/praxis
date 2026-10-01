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
3. Resolve listed blockers explicitly. Shell startup functions/aliases are not
   mechanically rewritten. System policy is never removed. Inspect the target
   project for local `.codex`, `AGENTS.md`, skills or plugins that could reactivate
   retired workflows; do not recursively delete unrelated repositories.
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
5. Bootstrap activates only Praxis. The self-test runs immediately afterward. A
   failure leaves Praxis installed, with diagnostics and `ready: false`.

The archive contains `inventory.json`, service-state journals, incremental
`moves.json` and either clean
baseline evidence or `recovery-required.json`. Do not blindly restore over newly
created files: inspect moves and rename the new setup aside before any explicit
restoration. Restoration is manual; Agentcore is never automatically reactivated.

The reset command and bootstrap are deliberately separate: an ordinary fresh
installation must not imply permission to erase existing customizations.
