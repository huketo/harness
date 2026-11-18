---
name: verify-hstack
description: Drive this repository's CLIs (the merge guard hook, harness-mode, the installer) in an isolated run directory and capture proof. Use to prove a change to plugin/, scripts/, or skills/full-send/scripts/ beyond the unit tests.
---

# Verify hstack

hstack has no server. Its user-facing surface is three CLIs: the merge guard hook an agent's shell command passes through, `harness-mode`, and the installer. This skill drives the real files in this checkout against a synthetic `HOME`, so nothing reaches the machine's agent configuration. `mise run check` stays the first check; use this when a change needs the behavior observed end to end.

The helper is [`scripts/verify-hstack`](scripts/verify-hstack). Call it by absolute path; the commands below assume `V=$(git rev-parse --show-toplevel)/.agents/skills/verify-hstack/scripts/verify-hstack`.

## Launch

```bash
mise trust && mise install && mise run setup
RUN=$("$V" launch)
```

`launch` creates `var/verify/<timestamp>-<pid>/` with a synthetic `home/`, a synthetic full-send allowlist (`github.com/example-owner/*`), `repos/`, and `evidence/`, and prints its path. Runs are independent, so several can exist side by side. Ready means the path printed and `doctor` passes.

## Doctor

```bash
"$V" doctor "$RUN"
```

Read-only. It confirms that Node is the version `mise.toml` pins and that the run holds its synthetic allowlist, and it prints the checkout revision the proof belongs to. Run it first whenever a result looks wrong.

## Drive

Every command that reads agent configuration goes through `"$V" run "$RUN" -- <command>`, which pins `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `CLAUDE_CONFIG_DIR`, and `CODEX_HOME` to the run and drops the user's git configuration. The feature map in [`features/`](features/README.md) holds the recipe for each feature.

## Evidence

Write transcripts to `$RUN/evidence/<feature>.txt`: each command, its output, and its exit status. A proof shows the action and the resulting state, for example the mode that was set and the decision the guard then returned. `var/` is ignored by git, so quote the lines that carry the claim in the MR or PR; do not attach the directory.

## Cleanup

```bash
"$V" cleanup "$RUN"
```

It removes the run's synthetic home, configuration, state, and repositories, and keeps `evidence/`. It refuses any path that is not a run directory it created.

## Gotchas

- **The installed merge guard reads your own shell command.** A command line that spells a merge command, even as a quoted payload, is denied before it runs. Keep merge commands in a cases file and pass the file's path, as `guard` does.
- **`CLAUDE_CONFIG_DIR` is inherited from a Claude Code session.** Running the installer with only `HOME` replaced writes links into the real Claude configuration directory. Run it through `"$V" run`.
- **`mise` refuses an isolated `HOME`.** Resolve the pinned Node first with `NODE=$(mise which node)` and run `"$NODE" <script>` inside the run.
