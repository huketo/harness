/**
 * Routing case files (`scripts/skill-eval/routing/*.json`). Each key under
 * `skills` is a candidate whose description the classifier sees; its
 * `should_fire` prompts expect that skill and its `should_not_fire` prompts
 * name the skill (or `none`) they belong to instead. A prompt listed more than
 * once is classified once, so every listing must expect the same answer.
 *
 *   { "suite": "design-routing", "version": 1, "skills": {
 *       "imagegen": { "should_fire": ["..."], "should_not_fire": [{ "prompt": "...", "goes_to": "image-to-code" }] } } }
 */

import { KEY_PATTERN } from "../schema.ts";

export const NONE = "none";

export interface RoutePrompt {
	/** `p01`, `p02`, ... in the order the prompt first appears in the file. */
	id: string;
	prompt: string;
	/** A candidate name or `none`. */
	expected: string;
	/** Every place the file lists this prompt: under which skill, and whether as `should_fire`. */
	listedUnder: { skill: string; fires: boolean }[];
}

export interface Routing {
	suite: string;
	version: number;
	/** Candidate skill names in file order; each is read from `skills/<name>/SKILL.md`. */
	candidates: string[];
	prompts: RoutePrompt[];
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isText = (v: unknown): v is string => typeof v === "string" && v.trim() !== "";

/** Parses and validates a routing file; throws one error listing every problem. */
export function parseRouting(text: string, where: string): Routing {
	let raw: unknown;
	try {
		raw = JSON.parse(text);
	} catch (e) {
		throw new Error(`${where}: invalid JSON (${(e as Error).message})`);
	}
	const problems: string[] = [];
	if (!isObject(raw)) throw new Error(`${where}: the top level must be an object`);
	if (!isText(raw.suite) || !KEY_PATTERN.test(raw.suite)) problems.push(`suite must match ${KEY_PATTERN}`);
	if (!Number.isInteger(raw.version) || (raw.version as number) < 1) problems.push("version must be a positive integer");
	const skills = isObject(raw.skills) ? raw.skills : {};
	const candidates = Object.keys(skills);
	if (!candidates.length) problems.push("skills must name at least one candidate skill");

	const byText = new Map<string, RoutePrompt>();
	const add = (prompt: unknown, expected: string, skill: string, fires: boolean, at: string) => {
		if (!isText(prompt)) return problems.push(`${at} must be a non-empty string`);
		const seen = byText.get(prompt);
		if (!seen) {
			const id = `p${String(byText.size + 1).padStart(2, "0")}`;
			byText.set(prompt, { id, prompt, expected, listedUnder: [{ skill, fires }] });
		} else if (seen.expected !== expected) {
			problems.push(`"${prompt}" expects both ${seen.expected} and ${expected}`);
		} else seen.listedUnder.push({ skill, fires });
	};
	for (const name of candidates) {
		const entry = skills[name];
		if (!KEY_PATTERN.test(name)) problems.push(`skill name "${name}" must match ${KEY_PATTERN}`);
		if (!isObject(entry)) {
			problems.push(`${name} must be an object`);
			continue;
		}
		const fire = entry.should_fire;
		const away = entry.should_not_fire;
		if (!Array.isArray(fire) || !fire.length) problems.push(`${name}.should_fire must be a non-empty list`);
		if (!Array.isArray(away) || !away.length) problems.push(`${name}.should_not_fire must be a non-empty list`);
		(Array.isArray(fire) ? fire : []).forEach((p, i) => add(p, name, name, true, `${name}.should_fire[${i}]`));
		(Array.isArray(away) ? away : []).forEach((item, i) => {
			const at = `${name}.should_not_fire[${i}]`;
			if (!isObject(item)) return problems.push(`${at} must be {"prompt", "goes_to"}`);
			const to = item.goes_to;
			if (to === name) return problems.push(`${at} goes_to its own skill`);
			if (typeof to !== "string" || (to !== NONE && !candidates.includes(to)))
				return problems.push(`${at} goes_to unknown skill "${String(to)}"; use a key of skills or "${NONE}"`);
			add(item.prompt, to, name, false, `${at}.prompt`);
		});
	}
	if (problems.length) throw new Error(`${where}: routing file is invalid\n  ${problems.join("\n  ")}`);
	return { suite: raw.suite as string, version: raw.version as number, candidates, prompts: [...byText.values()] };
}
