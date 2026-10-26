// Contract tests for plugin/build.mjs. Output goes to temporary directories; the CLI validators run only when
// installed and never touch the real agent homes (agy validate reads the given path only).
import { afterAll, beforeAll, expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { build, defaultOut, diffTree, parseArgs, render } from "./build.mjs";

const BUILD = join(import.meta.dir, "build.mjs");
let out;
beforeAll(() => {
	out = mkdtempSync(join(tmpdir(), "harness-plugin-build-"));
});
afterAll(() => rmSync(out, { recursive: true, force: true }));

test("each host artifact carries its manifest, the merge guard, and its own extras", () => {
	const claude = render("claude");
	expect(Object.keys(claude).sort()).toEqual([
		".claude-plugin/marketplace.json",
		".claude-plugin/plugin.json",
		"agents/reviewer.md",
		"hooks/hooks.json",
		"hooks/merge-guard.mjs",
	]);
	const hook = JSON.parse(claude["hooks/hooks.json"]).hooks.PreToolUse[0];
	expect(hook.matcher).toBe("Bash");
	expect(hook.hooks[0].onFailure).toBe("block");
	expect(hook.hooks[0].command).toContain('"${CLAUDE_PLUGIN_ROOT}/hooks/merge-guard.mjs" --format claude');
	expect(JSON.parse(claude[".claude-plugin/marketplace.json"]).plugins[0].source).toBe("./");

	const agy = render("agy");
	expect(Object.keys(agy).sort()).toEqual(["hooks.json", "hooks/merge-guard.mjs", "plugin.json", "rules/AGENTS.md"]);
	expect(JSON.parse(agy["hooks.json"])["harness-merge-guard"].PreToolUse[0].matcher).toBe("run_command");
	expect(Object.keys(render("agy", { hooks: false })).sort()).toEqual(["plugin.json", "rules/AGENTS.md"]);
	expect(() => render("codex")).toThrow(/unknown host/);
});

test("rendering is deterministic and the guard is copied verbatim", () => {
	expect(render("claude")).toEqual(render("claude"));
	expect(render("agy")["hooks/merge-guard.mjs"]).toBe(readFileSync(join(import.meta.dir, "hooks/merge-guard.mjs"), "utf8"));
});

test("build writes stable host directories, --check reports drift, and a rebuild repairs it", () => {
	const first = build({ out, hosts: ["claude", "agy"], hooks: true, check: false });
	expect(first.stale).toBe(false);
	expect(first.result.claude.dir).toBe(join(out, "claude"));
	expect(diffTree(join(out, "agy"), render("agy"))).toEqual([]);
	writeFileSync(join(out, "agy", "stray.txt"), "x");
	writeFileSync(join(out, "agy", "plugin.json"), "{}");
	const check = spawnSync("node", [BUILD, "--out", out, "--host", "agy", "--check"], { encoding: "utf8" });
	expect(check.status).toBe(1);
	expect(JSON.parse(check.stdout).agy.changes).toEqual(["changed plugin.json", "extra stray.txt"]);
	expect(spawnSync("node", [BUILD, "--out", out, "--host", "agy"]).status).toBe(0);
	expect(spawnSync("node", [BUILD, "--out", out, "--check"]).status).toBe(0);
});

test("arguments are validated and the default output follows XDG_STATE_HOME", () => {
	expect(() => parseArgs(["--out", "relative"])).toThrow(/absolute/);
	expect(() => parseArgs(["--out", out, "--host", "codex"])).toThrow(/--host/);
	expect(defaultOut({ XDG_STATE_HOME: "/s" })).toBe("/s/harness/plugins");
	expect(defaultOut({ XDG_STATE_HOME: "rel" })).toMatch(/\.local\/state\/harness\/plugins$/);
	expect(spawnSync("node", [BUILD, "--bogus"]).status).toBe(2);
});

test("installed CLIs accept the artifacts", () => {
	build({ out, hosts: ["claude", "agy"], hooks: true, check: false });
	const agy = spawnSync("agy", ["plugin", "validate", join(out, "agy"), "--strict"], { encoding: "utf8" });
	if (agy.error) console.log("agy not installed; skipped");
	else expect(agy.status).toBe(0);
	const claude = spawnSync("claude", ["plugin", "validate", "--strict", join(out, "claude")], { encoding: "utf8" });
	if (claude.error) console.log("claude not installed; skipped");
	else expect(claude.status).toBe(0);
});
