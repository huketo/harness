#!/usr/bin/env node
// Builds the hstack plugin files from plugin/ for each agent CLI.
//   node plugin/build.mjs [--out DIR] [--host claude|agy]... [--no-hooks] [--check]
// claude: plugin/ is itself the Claude Code plugin root (the repository marketplace in .claude-plugin/ points at
//   it), so this writes only the two generated files, .claude-plugin/plugin.json and hooks/hooks.json, in place and
//   tracked in git. The version comes from the root package.json, which changesets bumps. --out does not apply.
// agy: a copy under <out>/agy/, default <out> = ${XDG_STATE_HOME:-~/.local/state}/hstack/plugins. The directory is
//   stable (no content hash) because agy copies it on install.
// --check compares the rendered files with their target and exits 1 on a difference without writing.
// Codex has no artifact: its plugins cannot ship rules, and plugin hooks run only after a per-hook trust hash is
// written to config.toml, so the Codex merge guard is codex/harness.rules instead (see docs/REPO.md).
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync, chmodSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { realpathSync } from "node:fs";

const SOURCE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(SOURCE);
export const HOSTS = ["claude", "agy"];

const json = (value) => `${JSON.stringify(value, null, 2)}\n`;
const read = (rel) => readFileSync(join(SOURCE, rel), "utf8");

/** manifest.json plus the version that changesets keeps in the root package.json. */
export function manifest() {
	const { version } = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));
	return { ...JSON.parse(read("manifest.json")), version };
}

/** `owner/name` of the GitHub repository the manifest names, which is also the marketplace source. */
export function repoSlug(meta = manifest()) {
	const match = /^https:\/\/github\.com\/([^/]+\/[^/]+?)(?:\.git)?\/?$/.exec(meta.repository ?? "");
	if (!match) throw new Error(`manifest repository is not a github.com URL: ${meta.repository}`);
	return match[1];
}

export function defaultOut(env = process.env) {
	const state = env.XDG_STATE_HOME && isAbsolute(env.XDG_STATE_HOME) ? env.XDG_STATE_HOME : join(homedir(), ".local/state");
	return join(state, "hstack/plugins");
}

/** Files of one host as { relative path: content }: the generated files for claude, the whole copy for agy. */
export function render(host, { hooks = true } = {}) {
	const meta = manifest();
	const files = {};
	switch (host) {
		case "claude":
			files[".claude-plugin/plugin.json"] = json({
				name: meta.name,
				version: meta.version,
				description: meta.description,
				author: meta.author,
				repository: meta.repository,
				license: meta.license,
			});
			if (hooks) {
				files["hooks/hooks.json"] = json({
					hooks: {
						PreToolUse: [
							{
								matcher: "Bash",
								hooks: [
									{
										type: "command",
										command: 'node "${CLAUDE_PLUGIN_ROOT}/hooks/merge-guard.mjs" --format claude',
										timeout: 10,
										onFailure: "block",
									},
								],
							},
						],
					},
				});
			}
			break;
		case "agy":
			files["plugin.json"] = json({
				$schema: "https://antigravity.google/schemas/v1/plugin.json",
				name: meta.name,
				version: meta.version,
				description: meta.description,
			});
			files["rules/AGENTS.md"] = read("rules/AGENTS.md");
			if (hooks) {
				files["hooks/merge-guard.mjs"] = read("hooks/merge-guard.mjs");
				// agy runs plugin hooks with `sh -c` from the directory that holds hooks.json.
				files["hooks.json"] = json({
					"hstack-merge-guard": {
						PreToolUse: [
							{
								matcher: "run_command",
								hooks: [{ type: "command", command: "node hooks/merge-guard.mjs --format agy", timeout: 10 }],
							},
						],
					},
				});
			}
			break;
		default:
			throw new Error(`unknown host: ${host}`);
	}
	return files;
}

export function digest(files) {
	const hash = createHash("sha256");
	for (const rel of Object.keys(files).sort()) hash.update(`${rel}\0${files[rel]}\0`);
	return hash.digest("hex");
}

function listFiles(dir, base = dir) {
	if (!existsSync(dir)) return [];
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? listFiles(path, base) : [relative(base, path)];
	});
}

/** Differences between rendered files and a directory, as `missing|changed|extra <path>` lines. */
export function diffTree(dir, files) {
	const onDisk = new Set(listFiles(dir));
	const changes = [];
	for (const rel of Object.keys(files).sort()) {
		if (!onDisk.has(rel)) changes.push(`missing ${rel}`);
		else if (readFileSync(join(dir, rel), "utf8") !== files[rel]) changes.push(`changed ${rel}`);
	}
	for (const rel of [...onDisk].sort()) if (!(rel in files)) changes.push(`extra ${rel}`);
	return changes;
}

/** Like diffTree, for files that live among other tracked files: reports only `missing` and `changed`. */
export function diffFiles(dir, files) {
	return Object.keys(files)
		.sort()
		.flatMap((rel) => {
			const path = join(dir, rel);
			if (!existsSync(path)) return [`missing ${rel}`];
			return readFileSync(path, "utf8") === files[rel] ? [] : [`changed ${rel}`];
		});
}

/** Write each of <files> under <dir> and leave every other file there alone. */
export function writeFiles(dir, files) {
	for (const [rel, content] of Object.entries(files)) {
		const path = join(dir, rel);
		mkdirSync(dirname(path), { recursive: true });
		writeFileSync(path, content);
	}
}

/** Replace <dir> with exactly <files>, through a sibling temporary directory and a rename. */
export function writeTree(dir, files) {
	const tmp = `${dir}.tmp-${process.pid}`;
	const old = `${dir}.old-${process.pid}`;
	rmSync(tmp, { recursive: true, force: true });
	for (const [rel, content] of Object.entries(files)) {
		const path = join(tmp, rel);
		mkdirSync(dirname(path), { recursive: true });
		writeFileSync(path, content);
		if (rel.endsWith(".mjs")) chmodSync(path, 0o755);
	}
	mkdirSync(dirname(dir), { recursive: true });
	if (existsSync(dir)) renameSync(dir, old);
	renameSync(tmp, dir);
	rmSync(old, { recursive: true, force: true });
}

export function parseArgs(argv) {
	const opts = { out: defaultOut(), hosts: [], hooks: true, check: false };
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		if (arg === "--out") opts.out = argv[++i];
		else if (arg === "--host") opts.hosts.push(argv[++i]);
		else if (arg === "--no-hooks") opts.hooks = false;
		else if (arg === "--check") opts.check = true;
		else throw new Error(`unknown argument: ${arg}`);
	}
	if (!opts.out || !isAbsolute(opts.out)) throw new Error("--out needs an absolute directory");
	if (opts.hosts.length === 0) opts.hosts = [...HOSTS];
	for (const host of opts.hosts) if (!HOSTS.includes(host)) throw new Error(`--host must be one of ${HOSTS.join(", ")}`);
	return opts;
}

export function build(opts) {
	const result = {};
	let stale = false;
	for (const host of opts.hosts) {
		const files = render(host, { hooks: opts.hooks });
		const inPlace = host === "claude";
		const dir = inPlace ? (opts.pluginRoot ?? SOURCE) : join(opts.out, host);
		const changes = inPlace ? diffFiles(dir, files) : diffTree(dir, files);
		if (changes.length && !opts.check) (inPlace ? writeFiles : writeTree)(dir, files);
		if (changes.length && opts.check) stale = true;
		result[host] = { dir, digest: digest(files), files: Object.keys(files).length, changes };
	}
	return { result, stale };
}

function main() {
	let opts;
	try {
		opts = parseArgs(process.argv.slice(2));
	} catch (error) {
		process.stderr.write(`build.mjs: ${error.message}\n`);
		process.exit(2);
	}
	const { result, stale } = build(opts);
	process.stdout.write(json(result));
	process.exit(stale ? 1 : 0);
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
