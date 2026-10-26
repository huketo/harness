#!/usr/bin/env node
// Installs the harness plugin artifacts and guardrail settings for the agent CLIs found on PATH.
//   node plugin/install.mjs [--dry-run] [--out DIR]
// Steps, each reported on one line like install.sh: build plugin/ into <out>; register <out>/claude as the
// `harness` directory marketplace and install harness@harness (Claude Code reads that folder live, so later
// builds need no reinstall); install <out>/agy with `agy plugin install` (a copy; agy 1.4.7 skips a symlinked
// plugin directory), retiring the old repo symlink; union plugin/guardrails.json deny rules into the Claude Code
// and agy settings files, keeping a one-time `.harness-bak` copy. Never removes a rule or a foreign plugin.
// Exit 1 when something needs a person (a foreign plugin of the same name, unreadable settings).
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, lstatSync, readFileSync, readlinkSync, realpathSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build, defaultOut, diffTree, render } from "./build.mjs";

const SOURCE = dirname(fileURLToPath(import.meta.url));
const REPO = dirname(SOURCE);
const NAME = "harness";
// Manifest descriptions this repository has shipped for the agy plugin; another description means another owner.
const LEGACY_AGY_DESCRIPTIONS = [
	"Personal harness for the Antigravity CLI: the always-on rules that keep this CLI aligned with the OMP and Claude Code setup.",
];

function which(bin, env) {
	return (env.PATH ?? "").split(":").some((dir) => dir && existsSync(join(dir, bin)));
}

function cli(argv, env) {
	const run = spawnSync(argv[0], argv.slice(1), { encoding: "utf8", env, timeout: 120_000 });
	if (run.error || run.status !== 0) throw new Error(`${argv.join(" ")} failed: ${(run.stderr || run.error?.message || "").trim()}`);
	return run.stdout;
}

function expandHome(rule, home) {
	return rule.replaceAll("${HOME}", home);
}

/** Union `rules` into settings[path...] (an array); returns the rules that were missing. */
export function unionRules(settings, path, rules) {
	let node = settings;
	for (const key of path.slice(0, -1)) node = node[key] ??= {};
	const last = path.at(-1);
	const current = Array.isArray(node[last]) ? node[last] : [];
	const missing = rules.filter((rule) => !current.includes(rule));
	node[last] = [...current, ...missing];
	return missing;
}

export function plan({ out, env = process.env, home = env.HOME ?? homedir(), repo = REPO }) {
	const steps = [];
	const add = (kind, text, apply) => steps.push({ kind, text, apply });

	const fresh = build({ out, hosts: ["claude", "agy"], hooks: true, check: true });
	for (const [host, info] of Object.entries(fresh.result)) {
		if (info.changes.length === 0) add("unchanged", `unchanged artifact: ${info.dir}`);
		else add("change", `build artifact: ${info.dir} (${info.changes.length} file change(s))`, () => build({ out, hosts: [host], hooks: true, check: false }));
	}

	const claudeDir = join(out, "claude");
	if (!which("claude", env)) add("skip", "claude not on PATH; Claude Code plugin skipped");
	else {
		const markets = JSON.parse(cli(["claude", "plugin", "marketplace", "list", "--json"], env));
		const market = markets.find((m) => m.name === NAME);
		if (!market) add("change", `register Claude marketplace: ${NAME} -> ${claudeDir}`, () => cli(["claude", "plugin", "marketplace", "add", claudeDir, "--scope", "user"], env));
		else if (resolve(market.path ?? market.installLocation ?? "") !== resolve(claudeDir))
			add("conflict", `Claude marketplace ${NAME} points at ${market.path ?? market.installLocation}; left as is`);
		else add("unchanged", `unchanged Claude marketplace: ${NAME} -> ${claudeDir}`);
		const plugins = JSON.parse(cli(["claude", "plugin", "list", "--json"], env));
		const installed = plugins.find((p) => p.id === `${NAME}@${NAME}` && p.scope === "user");
		if (!installed) add("change", `install Claude plugin: ${NAME}@${NAME} (user scope)`, () => cli(["claude", "plugin", "install", `${NAME}@${NAME}`, "--scope", "user"], env));
		else add("unchanged", `unchanged Claude plugin: ${NAME}@${NAME} reads ${installed.readFromFolder ?? installed.installPath}`);
	}

	const agyTarget = join(home, ".gemini/config/plugins", NAME);
	if (!which("agy", env)) add("skip", "agy not on PATH; Antigravity plugin skipped");
	else {
		let stat = null;
		try {
			stat = lstatSync(agyTarget);
		} catch {}
		const install = () => cli(["agy", "plugin", "install", join(out, "agy")], env);
		if (stat?.isSymbolicLink()) {
			const into = resolve(dirname(agyTarget), readlinkSync(agyTarget));
			if (into === repo || into.startsWith(`${repo}/`) || into.includes("/agy/config/plugins/harness")) {
				add("change", `retire symlinked agy plugin (agy 1.4.7 skips it): ${agyTarget} -> ${into}`, () => rmSync(agyTarget));
				add("change", `install agy plugin copy: ${join(out, "agy")}`, install);
			} else add("conflict", `${agyTarget} links to ${into}, which this repo did not install; left as is`);
		} else if (stat) {
			let plugin = {};
			try {
				plugin = JSON.parse(readFileSync(join(agyTarget, "plugin.json"), "utf8"));
			} catch {}
			const ours = JSON.parse(render("agy")["plugin.json"]).description;
			if (plugin.name !== NAME || ![ours, ...LEGACY_AGY_DESCRIPTIONS].includes(plugin.description))
				add("conflict", `${agyTarget} holds a plugin this repo did not ship (${plugin.name ?? "no manifest"}); left as is`);
			else if (diffTree(agyTarget, render("agy")).some((c) => !c.startsWith("extra "))) add("change", `refresh agy plugin copy: ${join(out, "agy")}`, install);
			else add("unchanged", `unchanged agy plugin: ${agyTarget}`);
		} else add("change", `install agy plugin copy: ${join(out, "agy")}`, install);
	}

	const guardrails = JSON.parse(readFileSync(join(SOURCE, "guardrails.json"), "utf8"));
	for (const target of guardrails.settings) {
		const file = expandHome(target.file, home);
		if (!existsSync(file)) {
			add("skip", `settings absent: ${file}`);
			continue;
		}
		let settings;
		try {
			settings = JSON.parse(readFileSync(file, "utf8"));
		} catch {
			add("conflict", `settings not valid JSON: ${file}; left as is`);
			continue;
		}
		const rules = target.rules.map((rule) => expandHome(rule, home));
		const missing = unionRules(structuredClone(settings), target.path, rules);
		if (missing.length === 0) add("unchanged", `unchanged ${target.path.join(".")} in ${file}`);
		else
			add("change", `add ${missing.length} ${target.path.join(".")} rule(s) to ${file}: ${missing.join(", ")}`, () => {
				const backup = `${file}.harness-bak`;
				if (!existsSync(backup)) copyFileSync(file, backup);
				const next = JSON.parse(readFileSync(file, "utf8"));
				unionRules(next, target.path, rules);
				writeFileSync(`${file}.tmp`, `${JSON.stringify(next, null, 2)}\n`);
				renameSync(`${file}.tmp`, file);
			});
	}
	return steps;
}

function main() {
	const argv = process.argv.slice(2);
	const dryRun = argv.includes("--dry-run");
	const outAt = argv.indexOf("--out");
	const out = outAt >= 0 ? argv[outAt + 1] : defaultOut();
	const unknown = argv.filter((arg, i) => arg !== "--dry-run" && arg !== "--out" && i !== outAt + 1);
	if (unknown.length || !out) {
		process.stderr.write("usage: node plugin/install.mjs [--dry-run] [--out DIR]\n");
		process.exit(2);
	}
	let steps;
	try {
		steps = plan({ out });
	} catch (error) {
		process.stderr.write(`plugin install: ${error.message}\n`);
		process.exit(1);
	}
	let conflicts = 0;
	for (const step of steps) {
		if (step.kind === "conflict") {
			conflicts++;
			process.stderr.write(`skipped: ${step.text}\n`);
		} else if (step.kind === "change") {
			if (dryRun) process.stdout.write(`would ${step.text}\n`);
			else {
				step.apply();
				process.stdout.write(`done: ${step.text}\n`);
			}
		} else process.stdout.write(`${step.text}\n`);
	}
	process.exit(conflicts ? 1 : 0);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
