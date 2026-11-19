#!/usr/bin/env node
// Claude Code SessionStart hook: hands rules/common.md to the session as additional context, the way Antigravity CLI
// loads the same file as a plugin rule. Claude Code plugins cannot ship rule files, so a hook carries them.
import { readFileSync } from "node:fs";

const additionalContext = readFileSync(new URL("../rules/common.md", import.meta.url), "utf8");
process.stdout.write(`${JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext } })}\n`);
