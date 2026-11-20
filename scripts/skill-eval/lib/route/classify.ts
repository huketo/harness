/**
 * Description-based routing: what the classifier sees and how its answer is
 * graded. The classifier gets every candidate's frontmatter description and
 * one user request, and answers with one skill name or `none`. Nothing here
 * loads a skill or watches an agent decide to use one.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { checkFrontmatter, frontmatterFields } from "../../../check-repo.ts";
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

/** YAML 1.2 double-quoted escapes other than `\x`, `\u`, and `\U`, which take 2, 4, and 8 hex digits. */
const YAML_ESCAPES: Record<string, string> = {
	"0": "\0",
	a: "\x07",
	b: "\b",
	t: "\t",
	"\t": "\t",
	n: "\n",
	v: "\v",
	f: "\f",
	r: "\r",
	e: "\x1b",
	" ": " ",
	'"': '"',
	"/": "/",
	"\\": "\\",
	N: "\u0085",
	_: "\u00a0",
	L: "\u2028",
	P: "\u2029",
};

/** The text of a one-line YAML double-quoted scalar, quotes included. */
function yamlDoubleQuoted(raw: string): string {
	return raw.slice(1, -1).replace(/\\(x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}|.)/g, (whole, escape: string) => {
		if (escape.length > 1) return String.fromCodePoint(Number.parseInt(escape.slice(1), 16));
		const value = YAML_ESCAPES[escape];
		if (value === undefined) throw new Error(`invalid YAML escape ${whole} in ${raw}`);
		return value;
	});
}

/**
 * The `description` value of a SKILL.md whose frontmatter `checkFrontmatter`
 * accepted: a double-quoted, single-quoted, plain, or block scalar. A repeated
 * key reads its last line, as YAML loaders do.
 */
export function descriptionOf(skillMd: string): string {
	const fields = frontmatterFields(skillMd);
	const field = Array.isArray(fields) ? fields.findLast((f) => f.key === "description") : undefined;
	if (!field) throw new Error("no description key in the frontmatter");
	let text: string;
	if (field.block !== null) text = field.block.split(/\s+/).join(" ");
	else if (field.raw.startsWith('"')) text = yamlDoubleQuoted(field.raw);
	else if (field.raw.startsWith("'")) text = field.raw.slice(1, -1).replaceAll("''", "'");
	else text = field.raw;
	// A NUL cannot be passed to the CLI as an argument, so it is refused here with the file's name.
	if (text.includes("\0")) throw new Error("the description holds a NUL character");
	return text;
}

/**
 * Where Claude Code reads managed (administrator) settings: each file and its `managed-settings.d/` drop-in folder.
 * Their hooks run even in --safe-mode.
 */
export const MANAGED_SETTINGS = [
	"/etc/claude-code",
	"/Library/Application Support/ClaudeCode",
	"/mnt/c/Program Files/ClaudeCode",
	"C:\\Program Files\\ClaudeCode",
];

/**
 * The managed settings files under the given folders (managed-settings.json and every non-hidden
 * managed-settings.d/*.json) that define hooks or a policy helper, or that cannot be listed, read or parsed and so
 * cannot be shown free of them. A managed hook runs in safe mode
 * and can add context before the first model turn, so a paid run refuses while any is found.
 */
export function managedHookFiles(dirs: readonly string[] = MANAGED_SETTINGS): string[] {
	const missing = (e: unknown) => (e as NodeJS.ErrnoException).code === "ENOENT";
	const found: string[] = [];
	const files: string[] = [];
	for (const dir of dirs) {
		files.push(join(dir, "managed-settings.json"));
		const dropIns = join(dir, "managed-settings.d");
		try {
			// Claude Code skips hidden files in the drop-in folder.
			files.push(...readdirSync(dropIns).filter((n) => n.endsWith(".json") && !n.startsWith(".")).sort().map((n) => join(dropIns, n)));
		} catch (e) {
			if (!missing(e)) found.push(dropIns); // a folder that cannot be listed cannot be shown free of hooks
		}
	}
	for (const p of files) {
		let text: string;
		try {
			text = readFileSync(p, "utf8");
		} catch (e) {
			if (!missing(e)) found.push(p);
			continue;
		}
		try {
			const settings = JSON.parse(text) as { hooks?: unknown; policyHelper?: unknown };
			const hooks = settings.hooks;
			// A policy helper supplies settings this check cannot read, hooks included.
			if ((hooks !== undefined && hooks !== null && Object.keys(hooks as object).length > 0) || settings.policyHelper !== undefined) found.push(p);
		} catch {
			found.push(p); // unreadable managed settings cannot be shown to be free of hooks
		}
	}
	return found;
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
		if (found.length) continue;
		try {
			skills.push({ name, description: descriptionOf(text) });
		} catch (e) {
			problems.push(`${path}: ${(e as Error).message}`);
		}
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

/**
 * `claude -p` arguments for one classification call, checked against Claude
 * Code 2.1.329: one turn, the router system prompt, and no tools, skills, slash
 * commands, or MCP servers. `--safe-mode` drops CLAUDE.md, auto-memory, hooks,
 * installed plugins, and other customizations while keeping the login, and an
 * empty `--setting-sources` loads no user, project, or local settings file.
 * Safe mode keeps the built-in plugins, so `ROUTE_SETTINGS` turns off the one
 * that loads AGENTS.md files. Managed (policy) settings and the hooks of
 * managed plugins still apply.
 */
export const ROUTE_SETTINGS = JSON.stringify({ enabledPlugins: { "cc-plugin-agents-md@builtin": false } });

export function routeArgs(opts: { request: string; model: string; effort: string | null }): string[] {
	const args = ["-p", opts.request, "--model", opts.model];
	if (opts.effort) args.push("--effort", opts.effort);
	args.push(
		"--output-format",
		"stream-json",
		"--verbose",
		"--safe-mode",
		"--setting-sources",
		"",
		"--settings",
		ROUTE_SETTINGS,
		"--max-turns",
		"1",
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
