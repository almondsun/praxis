# Manual weekly maintenance

1. Run `python3 -m praxis update`. It reads stable releases and prints their notes;
   it does not install, edit pins, spawn inference or commit anything.
2. Review upstream changes and migrations. Back up the local Engram database
   using its documented consistent backup/export mechanism before a database
   upgrade. Keep the database on local storage. Never downgrade a migrated
   database without restoring a compatible backup.
3. Update a working copy of `versions.lock.json`: exact stable tag, resolved
   commit, artifact URL and SHA-256. Match published release checksums; for the
   Superpowers source archive bind the URL to the exact commit and hash it.
   Never pin `main`, `latest`, beta or canary as an install source.
4. Run unit tests, bootstrap and the live self-test. Review effective config and
   dependency changes. New components must have a non-overlapping responsibility.
5. Only after validation succeeds mark the new lockfile approved and commit it
   manually. Preserve the previous lockfile and database/config backups for repair.

`approved: false` means the resolved set has not yet completed all validation.
The bootstrap can install it for validation but cannot claim ready without a
matching successful self-test. The system never automatically promotes pins.

Do not run `gentle-ai upgrade`, marketplace upgrades or `mise up` against the
Praxis installation. Run installation through Praxis so pins and configuration
ownership are preserved. `doctor` detects modified managed configuration and
component files. Model availability may change independently of binaries; use
`doctor --runtime` and explicitly revise the routing policy when necessary.
