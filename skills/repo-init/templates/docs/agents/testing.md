# Focused verification

This guide lists the verification commands this repository defines and the file that defines each one. Select the narrowest command that proves the change; run the full suite when a change crosses several areas or the narrow command does not exist.

For behavior changes, test edits, flaky failures, or fixture and runner changes, use the `tdd` skill when it is available to the running agent. When a required runtime is missing, report the exact missing prerequisite and describe source inspection only as source inspection.

## Commands

| Purpose | Command | Defined in |
| --- | --- | --- |
{{COMMAND_ROWS}}

Pass a single test file or directory to the runner when it supports one, rather than running the whole suite for a local change.

## Not yet defined

{{MISSING_COMMANDS}}

When the repository gains one of these commands, add it to **Commands** with the file that defines it and remove it from this list.

## Commands with live effects

{{LIVE_EFFECT_COMMANDS}}

These are not routine verification. [`authority.md`](authority.md) governs when they may run.

## Delivery evidence

For each requested contract, report separately:

- the command and the selected test or scenario;
- pass, failure, or skip with the observed reason;
- whether dependencies were synthetic, temporary-local, installed on the machine, or live external;
- every relevant check not run;
- generated artifacts and whether they were removed or kept outside version control.

A successful command is evidence only for the boundary it exercised. Do not describe source review as a runtime pass, a dry run as a live operation, or a mocked suite as proof of an external service.
