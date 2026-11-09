#!/usr/bin/env node
// Plans the hstack plugin installation for the agent CLIs found on PATH; scripts/install.ts runs the steps.
//   node plugin/install.mjs [--dry-run] [--out DIR]   (standalone form, plugin steps only)
// Steps: register this repository's GitHub marketplace as `hstack`, install hstack@hstack at user scope, and turn
// marketplace auto-update on in <Claude config dir>/settings.json, so Claude Code fetches each released plugin
// version by itself (docs/guides/plugin-release.md); build the agy copy of plugin/ into <out>/agy and install it
// with `agy plugin install` (a copy, because agy skips a symlinked plugin directory). Leftovers of the earlier
// `harness` plugin are reported with the command that removes them. Never removes a marketplace, a plugin, or a
// setting. A foreign marketplace or plugin of the same name, or unreadable settings, is a conflict.
import { spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync, readlinkSync, realpathSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build, defaultOut, diffTree, render, repoSlug } from "./build.mjs";

const NAME = "hstack";
const LEGACY = "harness";
// Manifest descriptions this repository shipped for the agy plugin under the legacy name.
const LEGACY_AGY_DESCRIPTIONS = [
	"Personal harness guardrails: a work-mode merge guard, a read-only reviewer agent, and Antigravity rules.",
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

/**
 * Turn auto-update on for the marketplace `name` in a Claude Code settings object, declaring the marketplace
 * when the entry is absent. A value a person set, true or false, stays. Returns whether anything changed.
 */
export function ensureAutoUpdate(settings, name, source) {
	const entries = (settings.extraKnownMarketplaces ??= {});
	const entry = (entries[name] ??= { source });
	if (entry.autoUpdate !== undefined) return false;
	entry.autoUpdate = true;
	return true;
}

/**
 * Rewrite a settings file through `mutate`, keeping a timestamped `.hstack-bak-<time>` copy. A symlinked file is
 * written through to its target so the link survives; the file keeps its mode, and a new file is created 0600.
 */
function rewriteSettings(file, mutate) {
	const real = existsSync(file) ? realpathSync(file) : file;
	const mode = existsSync(real) ? statSync(real).mode & 0o777 : 0o600;
	if (existsSync(real)) copyFileSync(real, `${real}.hstack-bak-${new Date().toISOString().replace(/[:.]/g, "-")}`);
	const next = existsSync(real) ? JSON.parse(readFileSync(real, "utf8")) : {};
	mutate(next);
	mkdirSync(dirname(real), { recursive: true });
	const tmp = `${real}.tmp-${process.pid}`;
	writeFileSync(tmp, `${JSON.stringify(next, null, 2)}\n`, { mode });
	chmodSync(tmp, mode);
	renameSync(tmp, real);
}

function claudeSteps({ env, claudeDir, add }) {
	const slug = repoSlug();
	const markets = JSON.parse(cli(["claude", "plugin", "marketplace", "list", "--json"], env));
	const market = markets.find((m) => m.name === NAME);
	const foreign = market && !(market.source === "github" && market.repo === slug);
	if (!market) add("change", `register Claude marketplace: ${NAME} -> github:${slug}`, () => cli(["claude", "plugin", "marketplace", "add", slug, "--scope", "user"], env));
	else if (!foreign) add("unchanged", `unchanged Claude marketplace: ${NAME} -> github:${slug}`);
	else {
		const from = `${market.source ?? ""} ${market.repo ?? market.path ?? market.url ?? ""}`.trim();
		add("conflict", `Claude marketplace ${NAME} comes from ${from}, not github:${slug}; left as is`);
	}

	// A foreign marketplace of the same name is not ours to install from or to configure.
	const plugins = JSON.parse(cli(["claude", "plugin", "list", "--json"], env));
	const installed = plugins.find((p) => p.id === `${NAME}@${NAME}` && p.scope === "user");
	if (installed) add("unchanged", `unchanged Claude plugin: ${NAME}@${NAME} (version ${installed.version ?? "unknown"})`);
	else if (foreign) add("skip", `Claude plugin ${NAME}@${NAME} not installed: its marketplace is not ours`);
	else add("change", `install Claude plugin: ${NAME}@${NAME} (user scope)`, () => cli(["claude", "plugin", "install", `${NAME}@${NAME}`, "--scope", "user"], env));

	// Registering the marketplace may create the settings file, so an absent file is created at apply time.
	const file = join(claudeDir, "settings.json");
	let settings = {};
	if (existsSync(file))
		try {
			settings = JSON.parse(readFileSync(file, "utf8"));
		} catch {
			settings = null;
		}
	const source = { source: "github", repo: slug };
	if (foreign) add("skip", `Claude marketplace ${NAME} not ours; auto-update left as is`);
	else if (!settings) add("conflict", `settings not valid JSON: ${file}; marketplace auto-update not set`);
	else if (!ensureAutoUpdate(structuredClone(settings), NAME, source)) add("unchanged", `unchanged Claude marketplace auto-update: ${NAME} in ${file}`);
	else add("change", `turn on Claude marketplace auto-update: ${NAME} in ${file}`, () => rewriteSettings(file, (next) => ensureAutoUpdate(next, NAME, source)));

	// The directory marketplace that earlier versions of this repository registered under the legacy name.
	const legacy = markets.find((m) => m.name === LEGACY && /\/harness\/plugins\/claude\/?$/.test(m.path ?? m.installLocation ?? ""));
	if (legacy) add("skip", `legacy Claude marketplace ${LEGACY} (${legacy.path ?? legacy.installLocation}) from an earlier install still loads ${LEGACY}@${LEGACY}; remove it with \`claude plugin marketplace remove ${LEGACY}\``);
}

function agySteps({ env, home, out, repo, add }) {
	const artifact = join(out, "agy");
	const fresh = build({ out, hosts: ["agy"], hooks: true, check: true }).result.agy;
	if (fresh.changes.length === 0) add("unchanged", `unchanged artifact: ${artifact}`);
	else add("change", `build artifact: ${artifact} (${fresh.changes.length} file change(s))`, () => build({ out, hosts: ["agy"], hooks: true, check: false }));

	const install = () => cli(["agy", "plugin", "install", artifact], env);
	const target = join(home, ".gemini/config/plugins", NAME);
	let stat = null;
	try {
		stat = lstatSync(target);
	} catch {}
	if (stat?.isSymbolicLink()) {
		const into = resolve(dirname(target), readlinkSync(target));
		add("conflict", `${target} links to ${into}; agy skips a symlinked plugin, and this repo did not create it; left as is`);
	} else if (stat) {
		let plugin = {};
		try {
			plugin = JSON.parse(readFileSync(join(target, "plugin.json"), "utf8"));
		} catch {}
		const ours = JSON.parse(render("agy")["plugin.json"]).description;
		if (plugin.name !== NAME || plugin.description !== ours) add("conflict", `${target} holds a plugin this repo did not ship (${plugin.name ?? "no manifest"}); left as is`);
		else if (diffTree(target, render("agy")).some((c) => !c.startsWith("extra "))) add("change", `refresh agy plugin copy: ${artifact}`, install);
		else add("unchanged", `unchanged agy plugin: ${target}`);
	} else add("change", `install agy plugin copy: ${artifact}`, install);

	const legacy = join(home, ".gemini/config/plugins", LEGACY);
	let legacyPlugin = null;
	try {
		legacyPlugin = lstatSync(legacy).isSymbolicLink() ? { link: resolve(dirname(legacy), readlinkSync(legacy)) } : JSON.parse(readFileSync(join(legacy, "plugin.json"), "utf8"));
	} catch {}
	const shipped = legacyPlugin && (legacyPlugin.link ? legacyPlugin.link === repo || legacyPlugin.link.startsWith(`${repo}/`) : legacyPlugin.name === LEGACY && LEGACY_AGY_DESCRIPTIONS.includes(legacyPlugin.description));
	if (shipped) add("skip", `legacy agy plugin ${LEGACY} from an earlier install still loads; remove it with \`agy plugin uninstall ${LEGACY}\``);
}

export function plan({ env = process.env, home = env.HOME ?? homedir(), claudeDir = env.CLAUDE_CONFIG_DIR || join(home, ".claude"), out = defaultOut(env), repo = dirname(dirname(fileURLToPath(import.meta.url))) } = {}) {
	const steps = [];
	const add = (kind, text, apply) => steps.push({ kind, text, apply });
	if (!which("claude", env)) add("skip", "claude not on PATH; Claude Code plugin skipped");
	else claudeSteps({ env, claudeDir, add });
	if (!which("agy", env)) add("skip", "agy not on PATH; Antigravity plugin skipped");
	else agySteps({ env, home, out, repo, add });
	return steps;
}

function main() {
	const argv = process.argv.slice(2);
	const dryRun = argv.includes("--dry-run");
	const outAt = argv.indexOf("--out");
	const out = outAt >= 0 ? argv[outAt + 1] : defaultOut();
	const unknown = argv.filter((arg, i) => arg !== "--dry-run" && arg !== "--out" && (outAt < 0 || i !== outAt + 1));
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
			process.stderr.write(`conflict: ${step.text}\n`);
		} else if (step.kind === "change") {
			if (dryRun) process.stdout.write(`would ${step.text}\n`);
			else {
				step.apply();
				process.stdout.write(`done: ${step.text}\n`);
			}
		} else process.stdout.write(`${step.kind === "skip" ? "skipped: " : ""}${step.text}\n`);
	}
	process.exit(conflicts ? 1 : 0);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
