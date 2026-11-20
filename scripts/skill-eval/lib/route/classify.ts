/**
 * Description-based routing: what the classifier sees and how its answer is
 * graded. The classifier gets every candidate's frontmatter description and
 * one user request, and answers with one skill name or `none`. Nothing here
 * loads a skill or watches an agent decide to use one.
 */

import { checkFrontmatter } from "../../../check-repo.ts";
import { git, resolveRef } from "../run/skills.ts";
import { NONE } from "./cases.ts";

export const ROUTE_TITLE = "Description-based routing";

export const ROUTE_SCOPE =
	"This check reads skill descriptions only: each prompt is classified once from the candidate skills' frontmatter descriptions, and it does not observe whether an agent actually activates or loads a skill.";

export const ROUTER_SYSTEM =
	"You route user requests to agent skills. You see only each skill's name and description. Answer with one skill name or none, and nothing else.";

export interface SkillDescription {
	name: string;
	description: string;
}

/**
 * The `description` value of a SKILL.md whose frontmatter `checkFrontmatter`
 * accepted: a double-quoted, single-quoted, plain, or block scalar.
 */
export function descriptionOf(skillMd: string): string {
	const lines = skillMd.split("\n");
	const end = lines.indexOf("---", 1);
	const at = lines.findIndex((line, i) => i > 0 && i < end && /^description:/.test(line));
	if (at < 0) throw new Error("no description key in the frontmatter");
	const value = (lines[at] ?? "").slice("description:".length).trim();
	if (/^[|>][+-]?\d*$/.test(value)) {
		const body: string[] = [];
		for (const line of lines.slice(at + 1, end)) {
			if (!/^(\s+\S|\s*$)/.test(line)) break;
			if (line.trim()) body.push(line.trim());
		}
		return body.join(" ");
	}
	// YAML double-quoted escapes used in this repository (\" \\ \n \uXXXX) read the same as JSON's.
	if (value.startsWith('"')) return JSON.parse(value) as string;
	if (value.startsWith("'")) return value.slice(1, -1).replaceAll("''", "'");
	return value;
}

/**
 * Reads `skills/<name>/SKILL.md` for each name at `ref` (never the working
 * tree). A frontmatter that `scripts/check-repo.ts` refuses is refused here
 * with its `path:line: message` lines.
 */
export function readDescriptions(repoRoot: string, ref: string, names: string[]): { sha: string; skills: SkillDescription[] } {
	const sha = resolveRef(repoRoot, ref);
	const problems: string[] = [];
	const skills: SkillDescription[] = [];
	for (const name of names) {
		const path = `skills/${name}/SKILL.md`;
		let text: string;
		try {
			text = git(["show", `${sha}:${path}`], repoRoot).toString("utf8");
		} catch {
			problems.push(`${path}: not found at ${sha}`);
			continue;
		}
		const found = checkFrontmatter(text, name);
		for (const p of found) problems.push(`${path}:${p.line}: ${p.message}`);
		if (!found.length) skills.push({ name, description: descriptionOf(text) });
	}
	if (problems.length) throw new Error(`skill descriptions at ${sha} are unusable\n  ${problems.join("\n  ")}`);
	return { sha, skills };
}

/** The single user message of one classification call. */
export function routeRequest(skills: SkillDescription[], prompt: string): string {
	return [
		"An agent has the skills listed below, one line per skill: its name, then its description. Decide which one skill the agent should load to handle the user's request, judging only from these descriptions. If no skill fits, the answer is none.",
		"",
		"Skills:",
		...skills.map((s) => `- ${s.name}: ${s.description}`),
		"",
		"<request>",
		prompt,
		"</request>",
		"",
		"Reply with exactly one skill name from the list, or none. Reply with the bare name only: no quotes, backticks, punctuation, or explanation.",
	].join("\n");
}

/** `claude -p` arguments for one classification call: no tools, no skills, no slash commands, the router system prompt. */
export function routeArgs(opts: { request: string; model: string; effort: string | null }): string[] {
	const args = ["-p", opts.request, "--model", opts.model];
	if (opts.effort) args.push("--effort", opts.effort);
	args.push(
		"--output-format",
		"stream-json",
		"--verbose",
		"--disable-slash-commands",
		"--no-session-persistence",
		"--strict-mcp-config",
		"--tools",
		"",
		"--system-prompt",
		ROUTER_SYSTEM,
	);
	return args;
}

/**
 * - `correct`: the expected skill, or `none` when none was expected.
 * - `wrong`: another candidate skill.
 * - `none`: `none` when a skill was expected.
 * - `malformed`: anything that is not a bare candidate name or `none`.
 * - `failed`: the call did not finish with an answer.
 */
export type Verdict = "correct" | "wrong" | "none" | "malformed" | "failed";
export const VERDICTS: Verdict[] = ["correct", "wrong", "none", "malformed", "failed"];

export function gradeAnswer(
	final: string | null,
	finished: boolean,
	expected: string,
	candidates: string[],
): { answer: string | null; verdict: Verdict } {
	if (!finished || final === null) return { answer: final, verdict: "failed" };
	const answer = final.trim();
	if (answer !== NONE && !candidates.includes(answer)) return { answer, verdict: "malformed" };
	if (answer === expected) return { answer, verdict: "correct" };
	return { answer, verdict: answer === NONE ? "none" : "wrong" };
}
