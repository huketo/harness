#!/usr/bin/env node
/**
 * Turns a skill's `evals/evals.json` into a suite the runner and grader accept:
 * every case without the skill, with it, and with `--previous <gitref>` also
 * with the earlier version. Calls no model.
 *
 *   node scripts/skill-eval/from-evals.ts --skill skills/<name> [--previous <gitref>]
 */

import { existsSync, readFileSync, realpathSync } from "node:fs";
import { basename, join, relative, resolve } from "node:path";
import { parseArgs } from "node:util";
import { type EvalsFile, validateEvals, writeSuite } from "./lib/evals.ts";
import { gitText } from "./lib/run/skills.ts";

export const USAGE = "usage: node scripts/skill-eval/from-evals.ts --skill skills/<name> [--previous <gitref>]";

export interface Deps {
	/** The checkout whose runner executes the suite; the skill must live in its `skills/`. */
	repoRoot: string;
	cwd: string;
	log: (line: string) => void;
	warn: (line: string) => void;
}

export function main(argv: string[], partial: Partial<Deps> = {}): number {
	const { cwd, log, warn } = { cwd: process.cwd(), log: console.log, warn: console.error, ...partial };
	let values: { skill?: string; previous?: string };
	try {
		({ values } = parseArgs({ args: argv, strict: true, options: { skill: { type: "string" }, previous: { type: "string" } } }));
		if (!values.skill) throw new Error("--skill is required");
	} catch (error) {
		warn(`${(error as Error).message}\n${USAGE}`);
		return 2;
	}
	// The runner materializes `skills/<name>` from a commit of its own checkout, so that is the only place a skill may be.
	const repoRoot = realpathSync(partial.repoRoot ?? gitText(["rev-parse", "--show-toplevel"], import.meta.dirname));
	const given = resolve(cwd, values.skill!);
	const skillDir = join(repoRoot, "skills", basename(given));
	if (!existsSync(given) || realpathSync(given) !== skillDir) {
		warn(`${given}: the runner executes skills of its own checkout only; name a directory directly under ${join(repoRoot, "skills")}`);
		return 1;
	}
	const evalsFile = join(skillDir, "evals", "evals.json");
	let data: EvalsFile;
	try {
		data = JSON.parse(readFileSync(evalsFile, "utf8"));
	} catch (error) {
		warn(`${evalsFile}: ${(error as Error).message}`);
		return 1;
	}
	const errors = validateEvals(data, skillDir);
	if (errors.length) {
		warn(`${evalsFile}: invalid; nothing was written`);
		for (const error of errors) warn(`  ${error}`);
		return 1;
	}
	const outDir = join(repoRoot, "var", "skill-eval", "suites", basename(skillDir));
	const suite = writeSuite(data, skillDir, outDir, { skillPath: `skills/${basename(skillDir)}`, previousRef: values.previous });
	const shown = relative(cwd, suite) || suite;
	log(`${data.evals.length} cases, arms: none, skill${values.previous ? ", previous" : ""}`);
	log(`suite: ${shown}`);
	log("The skill arms read committed files, not the working tree. Commit the skill, then:");
	log(`  node scripts/skill-eval/run.ts --suite ${shown} --effort high`);
	log("  node scripts/skill-eval/grade.ts --iteration-dir <the directory the run printed>");
	return 0;
}

if (import.meta.main) process.exit(main(process.argv.slice(2)));
