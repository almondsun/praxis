# Project entry

Praxis resolves the enclosing checkout root with system Git before considering
any initialization. Native SessionStart uses the same helper as `praxis start`
and recovery. A subdirectory belongs to that checkout; a linked worktree retains
its Git checkout root while existing upstream private identity may refer to the
primary checkout. Parent-home Engram configuration is not imported.

An existing valid root `.engram/config.json` or upstream private shared-Git
identity is reused without rewriting it. An absent binding is initialized by the
exact installed Engram executable's native `init`, without `--force`. Praxis then
calls only `mem_current_project` through a fresh native MCP process to verify the
canonical name/path. It does not fabricate observations, sessions or decisions.
An empty store can remain empty until real work produces a meaningful memory.
Store context being absent is distinct from project identity being unresolved.

Malformed JSON, duplicate keys, invalid names, symlinks, conflicting root/private
identities, or an existing subproject binding are explicit blockers. Praxis does
not normalize these files, overwrite them, select among multiple identities or
redirect work to a guessed project. Upstream supports monorepo subproject bindings;
this root-owned Praxis entry contract deliberately requires explicit scope review
before using one. Failed native initialization leaves its actual state available
for inspection; no success or automatic rollback is invented.

For an explicitly requested new project:

```sh
python3 -m praxis start /absolute/new-project "Build the approved bounded application" --greenfield
```

The declared root must be nonexistent or a pristine real directory. Git is
initialized without copying user templates, then Engram is initialized. No Git
commit is created. In an existing repository this operation reuses its actual
Git root and never creates a nested repository. Without greenfield intent,
non-Git entry produces one clear confirmation gate and does not mutate project
files. Home, filesystem/system roots, installation/configuration roots and
greenfield paths inside infrastructure state are forbidden automatic targets.

Pinned upstream `engram init` creates a normal `.engram/config.json` and does not
change `.gitignore` or commit it. Upstream documents that file as a repository
write-target binding. It may be tracked intentionally by the normal Superpowers
workflow, or intentionally ignored for a clone-local binding. Shared Git's
`engram-project-identity.json` is private metadata, not a tracked project file.
Praxis makes neither tracking choice automatically. No Engram Cloud/Git sync is
enabled by initialization; canonical names are upstream namespaces, not globally
unique repository identifiers.

Native trusted SessionStart emits `continue:false` with a concrete stop reason
when preparation fails. An exit-code-only hook error is not used as a stop gate.
Normal native hook consent still applies; untrusted/disabled hooks do not count
as validated startup. `praxis start` checks preparation before starting Codex too.

Controller-owned immutable review explicitly uses read-only sandbox, disabled
Engram MCP and `PRAXIS_PROJECT_ENTRY_MODE=read-only-review`: the startup hook does
not initialize or query memory in that mode. For a direct read-only inspection,
use that mode together with the native read-only sandbox and disabled Engram;
it is an explicit inspection mode, not a normal project-entry success claim.
Implementation invocations clear inherited inspection mode. Native workflow
reviewers remain fresh subagents and do not own project initialization.

Git/checkpoints remain authoritative and memory remains advisory. Initialization
adds no engineering workflow, retries, auto-commits, publication or deployment.
The immutable accepted Taskbox pilot is not modified or replayed by this change.
