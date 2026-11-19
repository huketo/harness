#!/usr/bin/env node
// Claude Code SessionStart hook: hands rules/common.md to the session as additional context, the way Antigravity CLI
// loads the same file as a plugin rule. Claude Code plugins cannot ship rule files, so a hook carries them.
import { readFileSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const RULES = join(dirname(dirname(fileURLToPath(import.meta.url))), "rules/common.md");

/** The hook's stdout for a rules text: a SessionStart additionalContext object, or "" when there is no text. */
export function output(text) {
	if (!text.trim()) return "";
	return `${JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: text } })}\n`;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
	process.stdout.write(output(readFileSync(RULES, "utf8")));
}
