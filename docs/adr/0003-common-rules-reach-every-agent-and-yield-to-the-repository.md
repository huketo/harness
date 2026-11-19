---
status: accepted
---

# Common rules reach every agent and yield to the repository

One short file, `plugin/rules/common.md`, holds the working rules that apply in every repository: restate the goal and the smallest change, read history before removing unexplained code, reproduce before fixing, fix where the fault starts, verify by running, and label each reported claim as measured, inferred, or assumed. The `hstack` plugin hands it to Claude Code through a SessionStart hook and to AGY as an always-on plugin rule, and `mise run install` links it to `~/.codex/AGENTS.md` when that file is absent or empty. The file defers to the repository's `AGENTS.md` and `docs/agents/`, which `repo-init` writes and which stay the detailed source for each repository.

This widens [ADR 0002](0002-hstack-marketplace-ships-guardrails-only.md): the plugin still packages no skills, and the rules it carries are now common to all three agents rather than AGY's alone. Before this, a repository without `repo-init` documents gave Claude Code and Codex no working rules at all.

## Considered options

- Keep the rules per repository only: no global defaults, so unprepared repositories get none.
- Install the rules into the user's `CLAUDE.md`: one more owner for a file the user writes, and no path to Codex or AGY.
