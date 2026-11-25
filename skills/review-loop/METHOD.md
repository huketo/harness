# Method

Read this before changing `SKILL.md` or the scripts. It records why the read-only check has its shape. Agents running the skill do not load it.

## Evidence it started from

- **The check failed on every round for a cause that was not the reviewer.** `tree-unchanged` compared the shared `config` file by one digest. The agent host writes `branch.<name>.t3-merge-base` (and, on GitHub, `gh-merge-base`) into that file when it makes the reviewer's worktree, which is after the snapshot. In one review the check reported `CHANGED git control files` after both rounds in which it was run, and each time the author read the config by hand and used the verdict anyway, which is the step a check exists to remove. In an earlier review the host made the worktrees in another repository and the check passed.
- **Other writers do the same.** A survey of the config files on one workstation found these entries written by tools, none by a reviewer: `branch.*.t3-merge-base`, `branch.*.t3-merge-base-ref`, `branch.*.gh-merge-base`, `branch.*.vscode-merge-base`, and `remote.*.glab-resolved`, `glab-resolved-base`, `glab-resolved-head` (always `base` or `head`). `git worktree add -b <name> origin/main` and `gh pr checkout` add `branch.<name>.remote` and `.merge`.
- **A reviewer's read commands write nothing.** Measured in temporary clones: `gh pr view`, `pr list`, `pr diff`, `pr checks`, `pr status`, `repo view`, and `glab mr list`, `mr view`, `mr diff`, `repo view`, `ci status`, `release list`, `issue list` left the config identical. Which `glab` command writes `glab-resolved*` was not reproduced; creating an MR was not tried.
- **The shell tests ran nowhere.** `mise run check` and CI run `node --test`; the `.test.sh` files were listed only as manual commands.

## Chosen rung

Rung 2, the tool: the check itself, rewritten in Node so its tests run in CI, comparing config entries with `git config --file <file> --list` instead of digesting the file. Entries on the `noteOnly` list are printed and pass; every other entry fails. A new tool that writes a new key fails the check once, visibly, and earns one line in that list.

## The higher rung that was tested and not taken

Enforcing read-only when the reviewer starts, instead of proving it afterwards, works on this machine and was measured:

- `codex/review.ts` denies writes and network (`--inspect-tools`: `"write": "denied", "network": "denied"`), and ran a review from inside a thread in eight seconds.
- Antigravity has no read-only switch: `--mode plan` blocked nothing, and `--sandbox` protected `.git/config` only when the workspace was the main worktree, not a linked one. Wrapped in `bwrap --ro-bind / /` with only its state directory writable, every write failed (worktree file, shared config, hook, home directory, commit) while the model call still worked. With `~/.config/gh`, `~/.config/glab-cli`, and `~/.ssh` masked, `gh` and `glab` were logged out and SSH access was refused; an HTTPS push was not tried.

It was not taken because the reviewer would no longer be a thread: its progress cannot be watched, it cannot be found later, and a host restart kills it. That was the owner's decision on 2026-11-26. `bwrap` is also Linux-only. If a reviewer is ever seen to write something, this is the rung to return to.

## Known limits

- The check is after the fact and local: it does not see writes outside the worktree and the shared git directory, and it does not prove that nothing was pushed or commented.
- `noteOnly` trusts `branch.*.*-merge-base` entries whatever their value. They name a branch for a tool's own bookkeeping; no git command reads them.
