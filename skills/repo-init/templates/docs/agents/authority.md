# Authority boundaries

This guide classifies the effects of work in this repository. It does not redefine how to contact a person: [`hitl.md`](hitl.md) owns questions, valid approval responses, and unattended-run behavior.

Explicit task instructions authorize the described work only. Silence, a timeout, ambiguous text, repository access, or success on a related operation grants no additional authority.

## Autonomous local work

Within the requested scope, an agent may read tracked source, edit repository files, create temporary local fixtures, and run focused checks that do not modify machine configuration, contact authenticated external services, invoke paid services, publish data, or change another repository. It may remove the temporary files it created.

Access to the checkout is not blanket authority to read credentials, ignored runtime output, logs, databases, or personal data. Read them only when the task explicitly requires that evidence.

## Approval that may cover one plan

When the complete set is known, one explicit approval may cover named reversible actions such as:

- Creating local commits or pushing named branches.
- Opening or updating a named merge request or pull request.
- Creating, commenting on, labelling, or closing named issues in the tracker described in [`issue-tracker.md`](issue-tracker.md).
- Running named authenticated or paid external checks.
- Applying a documented installation or configuration change to the machine.

Approval for one plan ends with that plan. A push does not authorize a merge, a release, or a later batch.

## Separate decision every time

These actions are hard to undo, publish material, or cross a durable boundary. Each requires an explicit decision naming the exact action:

- Merging, force-pushing a shared branch, rebasing published history, or deleting branches or tags.
- Selecting or changing license or copyright terms.
- Changing repository visibility, or publishing a release, package, or deployment.
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
