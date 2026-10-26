// Contract tests for plugin/install.mjs. Fake `claude` and `agy` executables come first on PATH and log their
// arguments; HOME and the artifact directory are temporary, so no real agent home is read or written.
import { afterEach, beforeEach, expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { chmodSync, cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { unionRules } from "./install.mjs";

const INSTALL = join(import.meta.dir, "install.mjs");
const REPO = dirname(import.meta.dir);
let root, home, bin, out, log;

const FAKE = (name) => `#!/bin/sh
echo "${name} $*" >> "$FAKE_LOG"
case "$*" in
  "plugin marketplace list --json") cat "$FAKE_STATE/markets.json" 2>/dev/null || echo '[]' ;;
  "plugin list --json") cat "$FAKE_STATE/${name}-plugins.json" 2>/dev/null || echo '[]' ;;
  "plugin install "/*) [ "${name}" = agy ] && rm -rf "$HOME/.gemini/config/plugins/harness" && cp -R "$3" "$HOME/.gemini/config/plugins/harness" ;;
esac
`;

beforeEach(() => {
	root = mkdtempSync(join(tmpdir(), "harness-plugin-install-"));
	home = join(root, "home");
	bin = join(root, "bin");
	out = join(root, "out");
	log = join(root, "cli.log");
	mkdirSync(join(home, ".claude"), { recursive: true });
	mkdirSync(join(home, ".gemini/antigravity-cli"), { recursive: true });
	mkdirSync(join(home, ".gemini/config/plugins"), { recursive: true });
	mkdirSync(bin);
	for (const name of ["claude", "agy"]) {
		writeFileSync(join(bin, name), FAKE(name));
		chmodSync(join(bin, name), 0o755);
	}
	writeFileSync(join(home, ".claude/settings.json"), JSON.stringify({ permissions: { deny: ["WebFetch"] }, model: "x" }));
	writeFileSync(join(home, ".gemini/antigravity-cli/settings.json"), JSON.stringify({ permissions: { deny: ["command(sudo)"] } }));
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

function run(...args) {
	return spawnSync("node", [INSTALL, "--out", out, ...args], {
		encoding: "utf8",
		env: { ...process.env, HOME: home, PATH: `${bin}:${process.env.PATH}`, FAKE_LOG: log, FAKE_STATE: root, XDG_STATE_HOME: "" },
	});
}
const calls = () => (existsSync(log) ? readFileSync(log, "utf8").trim().split("\n") : []);

test("dry run plans every step and changes nothing", () => {
	symlinkSync(join(REPO, "agy/config/plugins/harness"), join(home, ".gemini/config/plugins/harness"));
	const dry = run("--dry-run");
	expect(dry.status).toBe(0);
	expect(dry.stdout).toContain(`would build artifact: ${join(out, "claude")}`);
	expect(dry.stdout).toContain(`would register Claude marketplace: harness -> ${join(out, "claude")}`);
	expect(dry.stdout).toContain("would install Claude plugin: harness@harness (user scope)");
	expect(dry.stdout).toContain("would retire symlinked agy plugin");
	expect(dry.stdout).toContain("would add 8 permissions.deny rule(s)");
	expect(dry.stdout).toContain(`read_file(${home}/.config/gh)`);
	expect(existsSync(out)).toBe(false);
	expect(calls().every((c) => c.endsWith("--json"))).toBe(true);
	expect(JSON.parse(readFileSync(join(home, ".claude/settings.json"), "utf8")).permissions.deny).toEqual(["WebFetch"]);
});

test("apply builds, registers, installs, and unions settings once with a backup", () => {
	symlinkSync(join(REPO, "agy/config/plugins/harness"), join(home, ".gemini/config/plugins/harness"));
	const first = run();
	expect(first.status).toBe(0);
	expect(existsSync(join(out, "claude/.claude-plugin/plugin.json"))).toBe(true);
	expect(lstatSync(join(home, ".gemini/config/plugins/harness")).isDirectory()).toBe(true);
	expect(calls()).toContain(`claude plugin marketplace add ${join(out, "claude")} --scope user`);
	expect(calls()).toContain("claude plugin install harness@harness --scope user");
	expect(calls()).toContain(`agy plugin install ${join(out, "agy")}`);
	const claude = JSON.parse(readFileSync(join(home, ".claude/settings.json"), "utf8"));
	expect(claude.permissions.deny[0]).toBe("WebFetch");
	expect(claude.permissions.deny).toContain("Read(~/.ssh/**)");
	expect(claude.model).toBe("x");
	expect(JSON.parse(readFileSync(join(home, ".claude/settings.json.harness-bak"), "utf8")).permissions.deny).toEqual(["WebFetch"]);

	writeFileSync(join(root, "markets.json"), JSON.stringify([{ name: "harness", path: join(out, "claude") }]));
	writeFileSync(join(root, "claude-plugins.json"), JSON.stringify([{ id: "harness@harness", scope: "user", readFromFolder: join(out, "claude") }]));
	const second = run("--dry-run");
	expect(second.status).toBe(0);
	expect(second.stdout).not.toContain("would ");
	expect(second.stdout).toContain("unchanged Claude marketplace");
});

test("foreign entries are left alone and reported", () => {
	writeFileSync(join(root, "markets.json"), JSON.stringify([{ name: "harness", path: "/elsewhere" }]));
	symlinkSync("/elsewhere/plugin", join(home, ".gemini/config/plugins/harness"));
	writeFileSync(join(home, ".gemini/antigravity-cli/settings.json"), "{not json");
	mkdirSync(join(root, "foreign"), { recursive: true });
	writeFileSync(join(root, "foreign/plugin.json"), JSON.stringify({ name: "harness", description: "someone else's harness" }));
	const dry = run("--dry-run");
	expect(dry.status).toBe(1);
	expect(dry.stderr).toContain("Claude marketplace harness points at /elsewhere");
	expect(dry.stderr).toContain("which this repo did not install");
	expect(dry.stderr).toContain("settings not valid JSON");
	rmSync(join(home, ".gemini/config/plugins/harness"));
	cpSync(join(root, "foreign"), join(home, ".gemini/config/plugins/harness"), { recursive: true });
	const foreign = run("--dry-run");
	expect(foreign.stderr).toContain("holds a plugin this repo did not ship (harness)");
	expect(foreign.stdout).not.toContain("agy plugin");
});

test("a legacy agy copy this repo shipped is refreshed", () => {
	mkdirSync(join(home, ".gemini/config/plugins/harness/rules"), { recursive: true });
	writeFileSync(join(home, ".gemini/config/plugins/harness/plugin.json"), JSON.stringify({ name: "harness", description: "Personal harness for the Antigravity CLI: the always-on rules that keep this CLI aligned with the OMP and Claude Code setup." }));
	expect(run("--dry-run").stdout).toContain("would refresh agy plugin copy");
});

test("unionRules only appends missing rules", () => {
	const settings = { permissions: { deny: ["a"] } };
	expect(unionRules(settings, ["permissions", "deny"], ["a", "b"])).toEqual(["b"]);
	expect(settings.permissions.deny).toEqual(["a", "b"]);
	const empty = {};
	unionRules(empty, ["permissions", "deny"], ["x"]);
	expect(empty).toEqual({ permissions: { deny: ["x"] } });
});
