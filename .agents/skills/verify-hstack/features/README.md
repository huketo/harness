# hstack verification map

The maintained source for verifying hstack's user-facing behavior. Read this index, then use the matching feature file as the recipe.

## Baseline

- `RUN=$("$V" launch)` and `"$V" doctor "$RUN"` succeeded in this session.
- `NODE=$(mise which node)` resolved outside the run.
- Every synthetic repository comes from `"$V" repo "$RUN" <name> <origin>`. It carries a CI definition and a `verify-demo` skill, so `harness-mode set full-send` is not degraded for lack of them.
- Origins under `github.com/example-owner/` are on the run's allowlist; any other origin is not.

## Feature entry contract

Each feature file starts with an H1 and one paragraph on the user-visible behavior, then exactly four H2 sections in this order: `Sub-features`, `How to get to it (user POV)`, `Driving it with verify-hstack`, `Gotchas`.

## Features

- [Merge guard](merge-guard.md) covers the hook's decision for a shell command under each work mode.
- [Work mode](work-mode.md) covers `harness-mode` setting, degrading, and clearing a mode.
- [Install plan](install-plan.md) covers the installer's plan and a skills-only install.
