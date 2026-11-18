# Work mode

A person selects `full-send` or `full-stop` for one task. `harness-mode` records the mode in the worktree's git directory, degrades `full-send` to `full-stop` where a merge without a person is not allowed, and says why.

## Sub-features

- `mode-set` records `full-send` in an allowlisted repository that holds a CI definition and a verification skill.
- `mode-degrade-allowlist` records `full-stop` when the origin is not on the allowlist.
- `mode-degrade-readiness` records `full-stop` when the worktree lacks a CI definition or a verification skill, and lists what is missing.
- `mode-readiness` reports what the worktree lacks without changing the mode.
- `mode-clear` removes the record.

## How to get to it (user POV)

- Invoke `/full-send` or `/full-stop` in a thread; the skill runs `harness-mode set <mode>` first.
- Run `skills/full-send/scripts/harness-mode show`, `allowlist`, or `readiness` in a worktree.

## Driving it with verify-hstack

Preconditions: the baseline in [README.md](README.md), and `MODE=$(git rev-parse --show-toplevel)/skills/full-send/scripts/harness-mode`.

- **Set.** In `REPO=$("$V" repo "$RUN" demo https://github.com/example-owner/demo.git)`, run `(cd "$REPO" && "$V" run "$RUN" -- "$MODE" set full-send)`. The last line is `mode=full-send`, and `show` prints the same mode with the origin.
- **Degrade by allowlist.** In `OTHER=$("$V" repo "$RUN" other https://github.com/someone-else/demo.git)`, the same command prints `runs as full-stop` and ends with `mode=full-stop`.
- **Degrade by readiness.** Remove `$REPO/.agents` and set `full-send` again. The output lists `a verification skill` and ends with `mode=full-stop`; `readiness` starts with `not ready`.
- **Clear.** `(cd "$REPO" && "$V" run "$RUN" -- "$MODE" clear)` prints `mode=none`, and `$REPO/.git/harness-mode` no longer exists.
- **Proof.** Redirect the commands and their output to `$RUN/evidence/work-mode.txt`.

## Gotchas

- Run `harness-mode` through `"$V" run`; outside the run it reads the real allowlist of the machine.
- The readiness check sees only whether the files exist. It does not tell whether the CI definition runs any check.
