---
status: accepted
---

# The `hstack` marketplace ships guardrails; skills stay links

The repository root is the `hstack` Claude Code plugin marketplace, and its one plugin, `hstack`, carries only the guardrails: the merge-guard hook, the read-only reviewer agent, and the Antigravity rules. Skills are not packaged into the plugin; `mise run install` links them into `~/.agents/skills` and `~/.claude/skills` as before.

Claude Code namespaces plugin skills (`hstack:grilling`), which would rename every skill and break the skills that call each other by name, and Codex and Antigravity would still need a separate install path. Linking keeps one name and one mechanism for all three agents. The name `hstack` replaces the generic `harness` so that a second, private marketplace can be installed next to this one without a name clash.

## Considered options

- Package the skills into the plugin: one-step install for Claude Code users, at the cost of renamed skills and a second path for the other agents.
- Split the skills into several topic plugins: selective install, with the largest rename and maintenance cost.
