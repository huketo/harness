---
"hstack": minor
---

Add a question guard for Claude Code: a PreToolUse hook on `AskUserQuestion` returns a question that names code identifiers, source files, or ADR numbers to the agent, with instructions to ask in terms of what the person will see and do and to show the screen or prototype in an option preview.
