#!/usr/bin/env node
// Claude Code PreToolUse hook for AskUserQuestion: returns a question to the agent when it names implementation
// identifiers, so the person is asked in terms of what they will see and do (docs/agents/hitl.md, decision kind 2).
// It reads only the tool input and decides from the text alone.
import { readFileSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

const IDENTIFIER = [
	/\b[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+\b/g, // camelCase
	/\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b/g, // snake_case
	/\b[A-Za-z_][\w-]*(?:\/[\w.-]+)*\.(?:go|ts|tsx|js|mjs|py|rs|sql|ya?ml|json|toml|md)\b/g, // a source file
	/\bADR[ -]?\d+\b/g,
	/\b[A-Za-z_]\w*\(\)/g, // a call
];

/** Every string the person would read in one AskUserQuestion input, previews excluded. */
export function questionText(input) {
	const parts = [];
	for (const question of Array.isArray(input?.questions) ? input.questions : []) {
		parts.push(question?.question, question?.header);
		for (const option of Array.isArray(question?.options) ? question.options : []) parts.push(option?.label, option?.description);
	}
	return parts.filter((part) => typeof part === "string").join("\n");
}

/** The implementation identifiers in a text, each once, in order of appearance. */
export function identifiers(text) {
	const found = [];
	for (const pattern of IDENTIFIER) for (const match of text.matchAll(pattern)) found.push([match.index, match[0]]);
	return [...new Set(found.sort((a, b) => a[0] - b[0]).map(([, term]) => term))];
}

export function decide(input) {
	const terms = identifiers(questionText(input));
	if (terms.length === 0) return { action: "allow" };
	return {
		action: "deny",
		reason: [
			`harness question guard: this question names implementation identifiers (${terms.join(", ")}).`,
			"The person decides from what they will see and be able to do, not from how it is built.",
			"Rewrite it before asking again:",
			"1. Say what each choice lets the person do and what can go wrong for them, without these identifiers.",
			"2. If the choice is about how something looks or behaves, show it first: put the captured screen, terminal text, or running prototype in an option preview or send it to the person, then ask which is closer.",
			"3. If running the candidates can settle it, it is not a question: measure, choose, and report.",
			"Keep an identifier only when the person must type or recognise that exact name, and then say what it is.",
		].join("\n"),
	};
}

function main() {
	let payload;
	try {
		payload = JSON.parse(readFileSync(0, "utf8"));
	} catch {
		return;
	}
	if (payload?.tool_name !== "AskUserQuestion") return;
	const decision = decide(payload.tool_input);
	if (decision.action !== "deny") return;
	process.stdout.write(
		`${JSON.stringify({ hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: decision.reason } })}\n`,
	);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
