# Method

Read this before changing `SKILL.md` or the scripts. It records why the procedure has its shape. Agents running the skill do not load it.

## Evidence it started from

- **Landed work was never cleaned up.** In a repository where agents had merged for weeks, most local branches were task and reviewer branches whose work had already landed. The agents gave two reasons for skipping the cleanup: the worktree they ran in could not delete itself, and the reviewer worktrees were not theirs.
- **A prose step fixed it twice, and no further.** After `docs/agents/workflow.md` gained "then run `sweep-landed.mjs --apply`", the next two merges ran the sweep. `SKILL.md` did not carry the step, and a repository without that workflow file had nothing that asked for it.

- **Reviewer worktrees were never swept.** A reviewer only reads, so its worktree keeps looking like a task that just started: clean, with a branch that never moved. The first merge that ran the sweep by itself kept four of them. `sweep-landed.mjs` now removes such a worktree once its branch has recorded nothing for 24 hours; `sweep-landed.test.mjs` holds the case.

## Chosen rung

Rung 2, the tool. `scripts/gated-merge.mjs` runs `scripts/sweep-landed.mjs --apply` after GitHub confirms the merge, so the cleanup no longer depends on an agent remembering a step. One sentence in step 6 of `SKILL.md` covers the merges that do not go through that script (a GitLab MR, a repository's own merge route).

Rung 1 does not apply: no check in a repository can see that a local branch of another clone was left behind.

## What was not done, and why

- **Nothing about captured output edited by hand.** A completion report once carried a terminal capture whose last line had been rewritten to match a later change. One observation is below the bar of two, and the rule it breaks belongs to `docs/agents/workflow.md` ("Deliver evidence") and `file-mr`, not to this skill.
- **No cases in `evals/evals.json`.** The runner copies plain files into a workspace. Every step this skill adds happens against a remote, a PR, CI, and an allowlist, which files cannot stand in for, and the skill is `disable-model-invocation`. The scripts carry the evidence instead: `gated-merge.test.mjs` and `sweep-landed.test.mjs` run against temporary repositories and a stand-in `gh`. The skill stays in `scripts/evals-owed.txt` until the runner can prepare a git state.

## Known limits

- `sweep-landed.mjs` recognises a squash merge only on GitHub. On GitLab it deletes a branch only when its tip is a commit of the default branch.
- The sentence in step 6 is unmeasured: no run compares a full-send merge with and without it.
