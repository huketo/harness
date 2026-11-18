# Merge guard

Before an agent's shell command runs, the guard decides whether it is a merge the current work mode allows. A person sees a merge go through, or sees the agent report that the guard denied it and why.

## Sub-features

- `guard-no-mode` denies a merge when no work mode is recorded.
- `guard-full-send` lets a merge of the allowlisted repository through.
- `guard-full-stop` denies every merge.
- `guard-admin` denies `--admin` in every mode.
- `guard-other-repo` denies a merge whose target is not the allowlisted repository.
- `guard-pass` ignores a command that is not a merge.

## How to get to it (user POV)

- An agent in Claude Code or Antigravity runs a shell command while the `hstack` plugin is enabled.
- A person records the mode by invoking `/full-send` or `/full-stop`, which run `harness-mode set`.

## Driving it with verify-hstack

Preconditions: the baseline in [README.md](README.md), `MODE=$(git rev-parse --show-toplevel)/skills/full-send/scripts/harness-mode` set while still in this checkout, and `REPO=$("$V" repo "$RUN" demo https://github.com/example-owner/demo.git)`.

- **No mode.** Run `"$V" guard "$RUN" "$REPO" .agents/skills/verify-hstack/features/merge-guard.cases`. The three merge lines print `deny`, the first with `no work mode allows merging`; `ls -la` prints `pass`.
- **Full send.** Run `(cd "$REPO" && "$V" run "$RUN" -- "$MODE" set full-send)`; it prints `mode=full-send`. Run the same `guard` command. The `--squash` line prints `pass`, the `--admin` line prints `deny` with `--admin bypasses branch protection`, and the `--repo other-owner/other` line prints `deny` with `is not on it`.
- **Full stop.** Run `(cd "$REPO" && "$V" run "$RUN" -- "$MODE" set full-stop)` and run `guard` again. Every merge line prints `deny` with `full-stop never merges`.
- **Proof.** Redirect the three `guard` runs and the two `set` commands to `$RUN/evidence/merge-guard.txt`.

To cover a new command shape, add its line to [`merge-guard.cases`](merge-guard.cases) and state the expected decision here.

## Gotchas

- Resolve `MODE` before `cd "$REPO"`. Inside the synthetic repository `git rev-parse --show-toplevel` names that repository, which has no `skills/`.
- `guard` drives the Claude Code payload format. The Codex and Antigravity formats are covered by `plugin/hooks/merge-guard.test.mjs` only.
- The guard reads the mode from the repository named in the payload's `cwd`, not from the directory `guard` runs in.
- A `pass` for a merge line means the guard printed nothing. It does not mean a merge happened; no merge command is executed.
