# Method

Read this before changing `SKILL.md` or the scripts. It records why the procedure has its shape. Agents running the skill do not load it.

## Evidence it started from

- **Landed work was never cleaned up.** On 2026-11-25 a private repository that agents had been merging in since early November held 113 local branches; 101 of them had landed (about 20 task branches and about 80 reviewer branches). The agents gave two reasons for skipping the cleanup: the worktree they ran in could not delete itself, and the reviewer worktrees were not theirs. Source: the owner's session of that day.
- **A prose step fixed it twice, and no further.** After `docs/agents/workflow.md` gained "then run `sweep-landed.mjs --apply`", the next two merges (one by a delegated agent, one in this repository) ran the sweep. `SKILL.md` did not carry the step, and a repository without that workflow file had nothing that asked for it.

## Chosen rung

Rung 2, the tool. `scripts/gated-merge.mjs` runs `scripts/sweep-landed.mjs --apply` after GitHub confirms the merge, so the cleanup no longer depends on an agent remembering a step. One sentence in step 6 of `SKILL.md` covers the merges that do not go through that script (a GitLab MR, a repository's own merge route).

Rung 1 does not apply: no check in a repository can see that a local branch of another clone was left behind.

## What was not done, and why

- **No rule about editing captured output.** On 2026-11-25 a delegated agent put a terminal capture in its completion report and rewrote the capture's last line by hand to match a message that a review round had changed. That is one observation, and the rule it breaks belongs to `docs/agents/workflow.md` ("Deliver evidence") and `file-mr`, not to this skill. A second observation is the bar for writing anything.
- **No cases in `evals/evals.json`.** The runner copies plain files into a workspace. Every step this skill adds happens against a remote, a PR, CI, and an allowlist, which files cannot stand in for, and the skill is `disable-model-invocation`. The scripts carry the evidence instead: `gated-merge.test.mjs` and `sweep-landed.test.mjs` run against temporary repositories and a stand-in `gh`. The skill stays in `scripts/evals-owed.txt` until the runner can prepare a git state.

## Known limits

- `sweep-landed.mjs` recognises a squash merge only on GitHub. On GitLab it deletes a branch only when its tip is a commit of the default branch.
- The sentence in step 6 is unmeasured: no run compares a full-send merge with and without it.
