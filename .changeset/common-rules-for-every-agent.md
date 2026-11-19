---
"hstack": minor
---

Ship the common working rules (`rules/common.md`) to Claude Code through a SessionStart hook and to Antigravity CLI as an always-on rule; they defer to each repository's `AGENTS.md` and `docs/agents/`. The Antigravity rules drop their verification section, which the common rules now carry.
