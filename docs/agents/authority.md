# Authority boundaries

This guide classifies repository operations performed for the owner. It does not redefine how to contact a person: [`hitl.md`](hitl.md) is authoritative for channel resolution, human-only decisions, message content, valid approval responses, and unattended-run behavior.

Explicit task instructions authorize the described work only. Silence, a timeout, ambiguous text, or success on a related operation grants no additional authority.

## Autonomous local work

Within the requested scope, an agent may inspect tracked source, edit repository-owned files, create temporary local fixtures, and run focused checks that do not modify host configuration, contact authenticated external services, invoke paid models, or publish data. It may redact evidence and remove task-created temporary files.

Local investigation follows data minimization. Access to the checkout is not blanket authority to inspect ignored `var/` output, home-directory sessions, credentials, reports, calendars, databases, or logs; read them only when the task explicitly requires that evidence.

## Actions that need no question

Within the requested scope these proceed without asking, and the final report names each one done:

- creating local commits, pushing the task's branch, and opening or updating its PR/MR;
- merging the task's PR/MR with the `full-send` skill's `scripts/gated-merge.mjs <number>`, which merges a GitHub PR only when CI passed on the current head, the description carries the `review-loop` approval line from a reviewer of another model family, and the repository is on the person's allowlist (`${XDG_CONFIG_HOME:-~/.config}/harness/full-send-repos`); when it refuses, as it does for every GitLab MR, the merge is a separate decision;
- re-running a failed CI job of the task's PR/MR to diagnose the failure;
- deleting the task's own branch and worktree after its PR/MR is merged, and the local branches and worktrees that the `full-send` skill's `scripts/sweep-landed.mjs` finds landed.

## Approval that may cover one plan

When the complete set is known, request one explicit approval covering named reversible actions such as:

- running named paid-model or authenticated external-service checks;
- inspecting named sensitive host, session, report, or calendar sources needed for the task;
- applying a documented installation or configuration change to the owner's host.

Approval for one batch ends with that plan and does not authorize a later batch or a wider target.

## Separate decision every time

These actions are hard to undo or cross a durable authority boundary. They require an explicit decision naming the exact action:

- changing license or copyright terms;
- publishing or unpublishing a repository, release, or package;
- counting a failed check as passed by re-running it until it passes, skipping it, or bypassing it;
- force-pushing a shared branch, rebasing published history, deleting tags or a branch the task does not own, or otherwise rewriting shared history;
- rotating or revoking credentials or editing secret stores;
- deleting preserved sessions, reports, audit evidence, benchmark data, or blocked host-sync candidates;
- starting, changing, enabling, or disabling scheduled jobs and live automations;
- submitting content, sending a notification, or performing another live external write, except the actions listed under [Actions that need no question](#actions-that-need-no-question);
- changing external project settings, access control, billing, or provider configuration.

## Work modes

A person may select a work mode for one task or thread with the `full-send` or `full-stop` skill; the mode is never a default. Without a selected mode, every rule in this guide applies unchanged.

- `full-stop` authorizes the task's own commits, pushes, rebases, and `--force-with-lease` on the task branch, and the test methods its proof needs. It never merges.
- `full-send` adds merging that one PR/MR once the skill's merge gate passes, only in a repository the person listed in `${XDG_CONFIG_HOME:-~/.config}/harness/full-send-repos`. The worktree must also hold a CI definition and a `verify-*` skill, so that a change can be proven without a person. Without the allowlist entry or either of those it runs as `full-stop` and says so.
- Neither mode authorizes deleting data, production changes, writes outside the repository, closing a PR/MR, admin bypass, force-pushing another branch, or editing the allowlist.

`skills/full-send/scripts/harness-mode` records the mode for the merge-guard hook, which blocks merge commands the mode does not allow; `gated-merge.mjs` is the route that needs no mode. The hook is a guardrail against accidental merges, not an authorization source: an explicit request for one merge is recorded with `harness-mode allow-merge <ref>` only after the person made it.

## Settled policy

The root MIT license and no-contributions policy are settled repository policy, not per-task decisions. Changing either still requires an explicit owner instruction. This public project does not use issues, pull requests, support requests, or vulnerability reports as inbound work channels.

## Host and external boundaries

`mise run install` changes skill and rule links, merges the `.rulesync` deny rules into the Claude Code and AGY settings files, and installs the `hstack` plugin into Claude Code and AGY. Foreign or unexpected entries remain conflicts and are preserved. Run it, and `mise run update`, only under explicit host-change authority. `mise run plan` inspects machine state without changing it and therefore still requires the task to permit host inspection. A plugin release reaches every machine that auto-updates the marketplace, so it is a publication ([`plugin-release.md`](../guides/plugin-release.md)).

Benchmark runs can invoke paid providers. Cron commands can alter unattended behavior. Treat each boundary according to its effects rather than inferring safety from a command name or dry run.

The distributed `t3/scheduled/jobs.json` is empty and grants no scheduling authority. Creating, enabling, or changing a T3 scheduled task is a schedule change. Example configuration snapshots do not authorize copying host configuration into the repository or restoring the example onto a host.

## Evidence does not expand authority

A review, test, diagnosis, dry run, or generated plan is evidence, not permission to write remotely or widen scope. Ground recommendations with a source location, focused reproduction and output, or primary reference. Name the observation that would overturn a recommendation and distinguish reversible cost from irreversible cost.

When approval is unavailable, finish every independent authorized part, leave repository and runtime state consistent, and report the exact blocked action and evidence. In unattended work, follow the runtime's human-in-the-loop owner: do not invoke the human channel; place the blocker in run output.
