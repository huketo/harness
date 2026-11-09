// The one installation entry point (`mise run plan`, `mise run install`).
//   node scripts/install.ts [--apply] [--skills-only]
// Without --apply it prints what would change and writes nothing. Three parts, each reported one line per step:
//   1. links: skills into ~/.agents/skills and <Claude config>/skills, the agy skill and rule slots, Codex rules;
//   2. permissions: .rulesync credential denies merged into Claude Code and agy settings (scripts/safe-generate.ts);
//   3. plugins: the hstack Claude Code marketplace and plugin, and the agy plugin copy (plugin/install.mjs).
// --skills-only stops after the skill links. Exit 1 when a step needs a person (a conflict, a lossy permission
// change, a missing rulesync); everything else is still processed.
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { planLinks, type Step } from "./links.ts";
import { applyPlan, findRulesync, generate } from "./safe-generate.ts";

const REPO = dirname(dirname(fileURLToPath(import.meta.url)));

export interface InstallOptions {
	repo?: string;
	home?: string;
	claudeDir?: string;
	apply?: boolean;
	skillsOnly?: boolean;
	env?: NodeJS.ProcessEnv;
	print?: (line: string) => void;
}

function report(step: Step, apply: boolean, print: (line: string) => void) {
	if (step.kind === "change") print(apply ? `done: ${step.text}` : `would ${step.text}`);
	else if (step.kind === "unchanged") print(step.text);
	else print(`${step.kind === "conflict" ? "conflict:" : "skipped:"} ${step.text}`);
}

/** Runs the steps in order; returns the number of steps that need a person. */
function run(steps: Step[], apply: boolean, print: (line: string) => void): number {
	let blocked = 0;
	for (const step of steps) {
		if (step.kind === "conflict") blocked++;
		if (step.kind === "change" && apply) {
			try {
				step.apply?.();
			} catch (error) {
				blocked++;
				print(`failed: ${step.text}: ${(error as Error).message}`);
				continue;
			}
		}
		report(step, apply, print);
	}
	return blocked;
}

function permissionSteps(repo: string, home: string, claudeDir: string): Step[] {
	const rulesync = findRulesync(repo);
	if (!rulesync) return [{ kind: "conflict", text: "rulesync is not installed; run `mise install` in this checkout" }];
	const plan = generate({ repo, home, claudeDir, rulesync });
	// rulesync warns that it overwrites existing entries of a category; generate() puts those entries back.
	const steps: Step[] = plan.log.filter((line) => !/will overwrite .* existing/.test(line)).map((line) => ({ kind: "skip", text: `rulesync: ${line}` }));
	for (const target of plan.skipped) steps.push({ kind: "skip", text: `${target} not installed; its permissions left as is` });
	if (!plan.files.length) steps.push({ kind: "unchanged", text: "unchanged permissions: every agent settings file already holds the .rulesync denies" });
	for (const file of plan.files) {
		const detail = [`+${file.added.length}`, file.restored.length ? `kept ${file.restored.length} existing` : "", file.lost.length ? `-${file.lost.length}` : ""].filter(Boolean).join(", ");
		if (file.lost.length)
			steps.push({
				kind: "conflict",
				text: `permissions in ${file.target} would lose existing settings (${file.lost.join("; ")}); add them to .rulesync or remove them by hand`,
			});
		else
			steps.push({
				kind: "change",
				text: `update permissions in ${file.target} (${detail})${file.added.length ? `: ${file.added.slice(0, 8).join(", ")}${file.added.length > 8 ? ", ..." : ""}` : ""}`,
				apply: () => applyPlan({ ...plan, files: [file] }),
			});
	}
	return steps;
}

export async function install(opts: InstallOptions = {}): Promise<number> {
	const env = opts.env ?? process.env;
	const repo = opts.repo ?? REPO;
	const home = opts.home ?? env.HOME ?? homedir();
	const claudeDir = opts.claudeDir ?? env.CLAUDE_CONFIG_DIR ?? join(home, ".claude");
	const apply = opts.apply ?? false;
	const print = opts.print ?? ((line: string) => console.log(line));

	let blocked = run(planLinks({ repo, home, claudeDir, skillsOnly: opts.skillsOnly }), apply, print);
	if (!opts.skillsOnly) {
		blocked += run(permissionSteps(repo, home, claudeDir), apply, print);
		const plugin = await import("../plugin/install.mjs");
		let steps: Step[];
		try {
			steps = plugin.plan({ env, home, claudeDir });
		} catch (error) {
			steps = [{ kind: "conflict", text: `plugin plan failed: ${(error as Error).message}` }];
		}
		blocked += run(steps, apply, print);
	}
	if (blocked) print(`\n${blocked} step(s) need a person; everything else was processed. Resolve them and rerun.`);
	else if (!apply) print("\nplan only: run `mise run install` to apply");
	return blocked ? 1 : 0;
}

if (import.meta.main) {
	const args = process.argv.slice(2);
	const unknown = args.filter((a) => !["--apply", "--skills-only"].includes(a));
	if (unknown.length || args.includes("--help")) {
		console.error("usage: node scripts/install.ts [--apply] [--skills-only]");
		process.exit(unknown.length ? 2 : 0);
	}
	process.exit(await install({ apply: args.includes("--apply"), skillsOnly: args.includes("--skills-only") }));
}
