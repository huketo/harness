// Contract tests for plugin/build.mjs. Output goes to temporary directories; the CLI validators run only when
// installed and never touch the real agent homes (agy validate reads the given path only).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, before, test } from "node:test";
import { build, defaultOut, diffFiles, diffTree, manifest, parseArgs, render, repoSlug } from "./build.mjs";

const BUILD = join(import.meta.dirname, "build.mjs");
const REPO = dirname(import.meta.dirname);
let out;
before(() => {
	out = mkdtempSync(join(tmpdir(), "hstack-plugin-build-"));
});
after(() => rmSync(out, { recursive: true, force: true }));

test("claude renders only the generated files; agy is a full copy with the guard and its rules", () => {
	const claude = render("claude");
	assert.deepEqual(Object.keys(claude).sort(), [".claude-plugin/plugin.json", "hooks/hooks.json"]);
	const hook = JSON.parse(claude["hooks/hooks.json"]).hooks.PreToolUse[0];
	assert.equal(hook.matcher, "Bash");
	assert.equal(hook.hooks[0].onFailure, "block");
	assert.ok(hook.hooks[0].command.includes('"${CLAUDE_PLUGIN_ROOT}/hooks/merge-guard.mjs" --format claude'));
	assert.deepEqual(Object.keys(render("claude", { hooks: false })), [".claude-plugin/plugin.json"]);

	const agy = render("agy");
	assert.deepEqual(Object.keys(agy).sort(), ["hooks.json", "hooks/merge-guard.mjs", "plugin.json", "rules/AGENTS.md"]);
	assert.equal(JSON.parse(agy["hooks.json"])["hstack-merge-guard"].PreToolUse[0].matcher, "run_command");
	assert.deepEqual(Object.keys(render("agy", { hooks: false })).sort(), ["plugin.json", "rules/AGENTS.md"]);
	assert.throws(() => render("codex"), /unknown host/);
});

test("one name and one version: package.json, plugin.json, and the root marketplace agree", () => {
	const pkg = JSON.parse(readFileSync(join(REPO, "package.json"), "utf8"));
	const plugin = JSON.parse(render("claude")[".claude-plugin/plugin.json"]);
	assert.equal(plugin.name, "hstack");
	assert.equal(plugin.version, pkg.version);
	assert.equal(manifest().version, pkg.version);
	assert.equal(repoSlug(), "huketo/harness");
	assert.throws(() => repoSlug({ repository: "https://example.com/x/y" }), /github\.com/);
	const market = JSON.parse(readFileSync(join(REPO, ".claude-plugin/marketplace.json"), "utf8"));
	assert.equal(market.name, plugin.name);
	assert.deepEqual(market.plugins.map((p) => [p.name, p.source]), [[plugin.name, "./plugin"]]);
	assert.deepEqual(diffFiles(import.meta.dirname, render("claude")), [], "run `node plugin/build.mjs --host claude` and commit the result");
});

test("rendering is deterministic and the guard is copied verbatim", () => {
	assert.deepEqual(render("claude"), render("claude"));
	assert.equal(render("agy")["hooks/merge-guard.mjs"], readFileSync(join(import.meta.dirname, "hooks/merge-guard.mjs"), "utf8"));
});

test("build writes a stable agy directory, --check reports drift, and a rebuild repairs it", () => {
	const first = build({ out, hosts: ["agy"], hooks: true, check: false });
	assert.equal(first.stale, false);
	assert.equal(first.result.agy.dir, join(out, "agy"));
	assert.deepEqual(diffTree(join(out, "agy"), render("agy")), []);
	writeFileSync(join(out, "agy", "stray.txt"), "x");
	writeFileSync(join(out, "agy", "plugin.json"), "{}");
	const check = spawnSync(process.execPath, [BUILD, "--out", out, "--host", "agy", "--check"], { encoding: "utf8" });
	assert.equal(check.status, 1);
	assert.deepEqual(JSON.parse(check.stdout).agy.changes, ["changed plugin.json", "extra stray.txt"]);
	assert.equal(spawnSync(process.execPath, [BUILD, "--out", out, "--host", "agy"]).status, 0);
	assert.equal(spawnSync(process.execPath, [BUILD, "--out", out, "--host", "agy", "--check"]).status, 0);
});

test("claude files are written in place among other files, and only they are compared", () => {
	const root = join(out, "claude-root");
	cpSync(import.meta.dirname, root, { recursive: true });
	writeFileSync(join(root, "hooks/hooks.json"), "{}");
	assert.deepEqual(build({ out, hosts: ["claude"], hooks: true, check: true, pluginRoot: root }).result.claude.changes, ["changed hooks/hooks.json"]);
	build({ out, hosts: ["claude"], hooks: true, check: false, pluginRoot: root });
	assert.deepEqual(diffFiles(root, render("claude")), []);
	assert.equal(readFileSync(join(root, "agents/reviewer.md"), "utf8"), readFileSync(join(import.meta.dirname, "agents/reviewer.md"), "utf8"));
});

test("arguments are validated and the default output follows XDG_STATE_HOME", () => {
	assert.throws(() => parseArgs(["--out", "relative"]), /absolute/);
	assert.throws(() => parseArgs(["--out", out, "--host", "codex"]), /--host/);
	assert.equal(defaultOut({ XDG_STATE_HOME: "/s" }), "/s/hstack/plugins");
	assert.match(defaultOut({ XDG_STATE_HOME: "rel" }), /\.local\/state\/hstack\/plugins$/);
	assert.equal(spawnSync(process.execPath, [BUILD, "--bogus"]).status, 2);
});

test("installed CLIs accept the artifacts", () => {
	build({ out, hosts: ["agy"], hooks: true, check: false });
	const agy = spawnSync("agy", ["plugin", "validate", join(out, "agy"), "--strict"], { encoding: "utf8" });
	if (agy.error) console.log("agy not installed; skipped");
	else assert.equal(agy.status, 0, `${agy.stdout}${agy.stderr}`);
	const claude = spawnSync("claude", ["plugin", "validate", "--strict", import.meta.dirname], { encoding: "utf8" });
	if (claude.error) console.log("claude not installed; skipped");
	else assert.equal(claude.status, 0, `${claude.stdout}${claude.stderr}`);
});
