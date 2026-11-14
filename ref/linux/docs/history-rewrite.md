# Applying the prepared repository history

The source tree is now named pmos-munch and contains only the postmarketOS
porting path and its hardware bring-up history. The requested Git replacement
is one clean initial commit, rather than a fabricated sequence of old commits.
[history.md](history.md) records the milestones and unfinished work honestly.

The rewrite helper first snapshots the reviewed sources and bundles all existing
Git refs under `out/rebrand-backup/`. It checks that HEAD, refs and file hashes
still match the reviewed plan before changing the repository. It rejects an
unexpected branch layout or remote configuration and never pushes anything.

Prepare the plan after source review:

```sh
python3 tools/rewrite-history.py --prepare
```

If the agent environment mounts `.git` read-only, apply the prepared plan from
a normal local terminal:

```sh
python3 tools/rewrite-history.py --apply --rename-directory
```

This replaces the current branch's visible history with one root commit, removes
the old tags after saving them in the bundle, and renames the project directory
to `pmos-munch`. Reopen the workspace at the new path. Path-dependent build
caches and the local pmbootstrap config may need a fresh output directory after
the move; existing boot images remain ordinary files and can still be booted.

The old history remains recoverable from the local bundle. Unreachable Git
objects/reflogs are not forcibly pruned. The backup directory is ignored and is
not included in the replacement commit.
