# Authority boundaries

This guide classifies the effects of work in this repository. It does not redefine how to contact a person: [`hitl.md`](hitl.md) owns questions, valid approval responses, and unattended-run behavior.

Explicit task instructions authorize the described work only. Silence, a timeout, ambiguous text, repository access, or success on a related operation grants no additional authority.

## Autonomous local work

Within the requested scope, an agent may read tracked source, edit repository files, create temporary local fixtures, and run focused checks that do not modify machine configuration, contact authenticated external services, invoke paid services, publish data, or change another repository. It may remove the temporary files it created.

Access to the checkout is not blanket authority to read credentials, ignored runtime output, logs, databases, or personal data. Read them only when the task explicitly requires that evidence.

## Actions that need no question

Within the requested scope these proceed without asking, and the final report names each one done:

- Creating local commits, pushing the task's branch, and opening or updating its PR/MR.
- Commenting on, labelling, or closing the issues the task works on, in the tracker described in [`issue-tracker.md`](issue-tracker.md).
- Merging the task's PR/MR with the `full-send` skill's `scripts/gated-merge.mjs <number>`, which merges a GitHub PR only when CI passed on the current head, the description carries the `review-loop` approval line from a reviewer of another model family, and the repository is on the person's allowlist (`${XDG_CONFIG_HOME:-~/.config}/harness/full-send-repos`); when it refuses, as it does for every GitLab MR, the merge is a separate decision.
- Re-running a failed CI job of the task's PR/MR to diagnose the failure.
- Deleting the task's own branch and worktree after its PR/MR is merged.
- Deploying to staging.

## Approval that may cover one plan

When the complete set is known, one explicit approval may cover named reversible actions such as:

- Running named authenticated or paid external checks.
- Applying a documented installation or configuration change to the machine.

Approval for one plan ends with that plan and does not authorize a later batch or a wider target.

## Separate decision every time

These actions are hard to undo, publish material, or cross a durable boundary. Each requires an explicit decision naming the exact action:

- Deploying to production, or publishing a release or package.
- Posting or sending anything from the person's external accounts, except the actions listed under [Actions that need no question](#actions-that-need-no-question).
- Counting a failed check as passed by re-running it until it passes, skipping it, or bypassing it.
- Force-pushing a shared branch, rebasing published history, or deleting tags or a branch the task does not own.
- Selecting or changing license or copyright terms.
- Changing repository visibility.
- Rotating or revoking credentials, or editing secret stores.
- Deleting data, preserved evidence, or another person's work.
- Creating, changing, or disabling CI pipelines, scheduled jobs, or live automations.
- Changing external project settings, access control, billing, or provider configuration.
{{PROJECT_DECISIONS}}

A task's own branch that no one else has fetched may be pushed with `--force-with-lease`; any other force-push is a separate decision.

## Work modes

A person may select a work mode for one task or thread with the `full-send` or `full-stop` skill; a mode is never a default. Without a selected mode, every rule in this guide applies unchanged. The mode's skill defines what it authorizes and in which repositories. A merge guard that blocks merges is a guardrail, not an authorization source.

## Evidence does not expand authority

A review, test, diagnosis, dry run, or generated plan is evidence, not permission to widen scope or publish. Classify each effect by what it does, not by a command's name or a `--dry-run` flag.

When authority is unavailable, finish every independent authorized part, leave the repository consistent, and report the exact blocked action and its evidence. In an unattended run, follow [`hitl.md`](hitl.md): place the blocker in the run output instead of asking.
