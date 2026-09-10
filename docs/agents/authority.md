# Authority boundaries

This guide classifies repository operations performed for the owner. It does not redefine how to contact a person: [`.omp/APPEND_SYSTEM.md`](../../.omp/APPEND_SYSTEM.md) is authoritative for channel resolution, human-only decisions, message content, valid approval responses, and unattended-run behavior.

Explicit task instructions authorize the described work only. Silence, a timeout, ambiguous text, or success on a related operation grants no additional authority.

## Autonomous local work

Within the requested scope, an agent may inspect tracked source, edit repository-owned files, create temporary local fixtures, and run focused checks that do not modify host configuration, contact authenticated external services, invoke paid models, or publish data. It may redact evidence and remove task-created temporary files.

Local investigation follows data minimization. Access to the checkout is not blanket authority to inspect ignored `var/` output, home-directory sessions, credentials, reports, calendars, databases, or logs; read them only when the task explicitly requires that evidence.

## Approval that may cover one plan

When the complete set is known, request one explicit approval covering named reversible actions such as:

- creating local commits or pushing a named owner branch;
- running named paid-model or authenticated external-service checks;
- inspecting named sensitive host, session, report, or calendar sources needed for the task;
- applying a documented installation or configuration change to the owner's host.

Approval for one batch ends with that plan and does not authorize a later batch or a wider target.

## Separate decision every time

These actions are hard to undo or cross a durable authority boundary. They require an explicit decision naming the exact action:

- changing license or copyright terms;
- publishing or unpublishing a repository, release, or package;
- merging, force-pushing, rebasing published history, deleting branches or tags, or otherwise rewriting shared history;
- rotating or revoking credentials or editing secret stores;
- deleting preserved sessions, reports, audit evidence, benchmark data, or blocked host-sync candidates;
- starting, changing, enabling, or disabling scheduled jobs and live automations;
- submitting content, sending a notification, or performing another live external write;
- changing external project settings, access control, billing, or provider configuration.

The root MIT license and no-contributions policy are settled repository policy, not per-task decisions. Changing either still requires an explicit owner instruction. This public project does not use issues, pull requests, support requests, or vulnerability reports as inbound work channels.

## Host and external boundaries

`bash install.sh` changes links and removes retired `harness-accounts` and `harness-native-compaction` links only when they are owned by this checkout; `--with-config` additionally applies managed OMP settings. Foreign or unexpected entries remain conflicts and are preserved. `omp/config.apply.sh` without `--check` changes live configuration. Run mutating forms only under explicit host-change authority. The documented `--dry-run` and `--check` forms inspect machine state without changing it and therefore still require the task to permit host inspection.

Benchmark runs can invoke paid providers. Daily-report collectors can authenticate to GitLab and read private calendar feeds; the final Daou Office entry and submission are human UI actions. Cron commands can alter unattended behavior. Treat each boundary according to its effects rather than inferring safety from a command name or dry run.

The distributed cron snapshot is empty and grants no scheduling authority. Example configuration snapshots do not authorize copying host configuration into the repository or restoring the example onto a host.

## Evidence does not expand authority

A review, test, diagnosis, dry run, or generated plan is evidence, not permission to write remotely or widen scope. Ground recommendations with a source location, focused reproduction and output, or primary reference. Name the observation that would overturn a recommendation and distinguish reversible cost from irreversible cost.

When approval is unavailable, finish every independent authorized part, leave repository and runtime state consistent, and report the exact blocked action and evidence. In unattended work, follow `.omp/APPEND_SYSTEM.md`: do not invoke the human channel; place the blocker in run output.
