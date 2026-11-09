// Contract tests for plugin/install.mjs. Fake `claude` and `agy` executables come first on PATH and log their
// arguments; HOME and the artifact directory are temporary, so no real agent home is read or written.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { repoSlug } from "./build.mjs";
import { ensureAutoUpdate } from "./install.mjs";

const INSTALL = join(import.meta.dirname, "install.mjs");
const SLUG = repoSlug();
let root, home, bin, out, log;

const FAKE = (name) => `#!/bin/sh
echo "${name} $*" >> "$FAKE_LOG"
case "$*" in
  "plugin marketplace list --json") cat "$FAKE_STATE/markets.json" 2>/dev/null || echo '[]' ;;
  "plugin list --json") cat "$FAKE_STATE/${name}-plugins.json" 2>/dev/null || echo '[]' ;;
  "plugin install "/*) [ "${name}" = agy ] && rm -rf "$HOME/.gemini/config/plugins/hstack" && cp -R "$3" "$HOME/.gemini/config/plugins/hstack" ;;
esac
`;

beforeEach(() => {
	root = mkdtempSync(join(tmpdir(), "hstack-plugin-install-"));
	home = join(root, "home");
	bin = join(root, "bin");
	out = join(root, "out");
	log = join(root, "cli.log");
	mkdirSync(join(home, ".claude"), { recursive: true });
	mkdirSync(join(home, ".gemini/config/plugins"), { recursive: true });
	mkdirSync(bin);
	for (const name of ["claude", "agy"]) {
		writeFileSync(join(bin, name), FAKE(name));
		chmodSync(join(bin, name), 0o755);
	}
	writeFileSync(join(home, ".claude/settings.json"), JSON.stringify({ permissions: { deny: ["WebFetch"] }, model: "x" }));
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

function run(args = [], extraEnv = {}) {
	return spawnSync(process.execPath, [INSTALL, "--out", out, ...args], {
		encoding: "utf8",
		env: { ...process.env, HOME: home, CLAUDE_CONFIG_DIR: "", PATH: `${bin}:${process.env.PATH}`, FAKE_LOG: log, FAKE_STATE: root, XDG_STATE_HOME: "", ...extraEnv },
	});
}
const calls = () => (existsSync(log) ? readFileSync(log, "utf8").trim().split("\n") : []);
const settings = (dir = join(home, ".claude")) => JSON.parse(readFileSync(join(dir, "settings.json"), "utf8"));

test("dry run plans every step and changes nothing", () => {
	const dry = run(["--dry-run"]);
	assert.equal(dry.status, 0, dry.stderr);
	assert.ok(dry.stdout.includes(`would register Claude marketplace: hstack -> github:${SLUG}`));
	assert.ok(dry.stdout.includes("would install Claude plugin: hstack@hstack (user scope)"));
	assert.ok(dry.stdout.includes("would turn on Claude marketplace auto-update: hstack"));
	assert.ok(dry.stdout.includes(`would build artifact: ${join(out, "agy")}`));
	assert.ok(dry.stdout.includes("would install agy plugin copy"));
	assert.equal(existsSync(out), false);
	assert.equal(calls().every((c) => c.endsWith("--json")), true);
	assert.deepEqual(settings(), { permissions: { deny: ["WebFetch"] }, model: "x" });
});

test("apply registers, installs, and turns auto-update on once with a backup; a second plan is unchanged", () => {
	const first = run();
	assert.equal(first.status, 0, first.stderr);
	assert.ok(calls().includes(`claude plugin marketplace add ${SLUG} --scope user`));
	assert.ok(calls().includes("claude plugin install hstack@hstack --scope user"));
	assert.ok(calls().includes(`agy plugin install ${join(out, "agy")}`));
	assert.equal(lstatSync(join(home, ".gemini/config/plugins/hstack")).isDirectory(), true);
	const claude = settings();
	assert.deepEqual(claude.extraKnownMarketplaces.hstack, { source: { source: "github", repo: SLUG }, autoUpdate: true });
	assert.deepEqual(claude.permissions.deny, ["WebFetch"]);
	assert.equal(claude.model, "x");
	assert.equal(readdirSync(join(home, ".claude")).filter((f) => f.startsWith("settings.json.hstack-bak-")).length, 1);

	writeFileSync(join(root, "markets.json"), JSON.stringify([{ name: "hstack", source: "github", repo: SLUG }]));
	writeFileSync(join(root, "claude-plugins.json"), JSON.stringify([{ id: "hstack@hstack", scope: "user", version: "0.1.0" }]));
	const second = run(["--dry-run"]);
	assert.equal(second.status, 0, second.stderr);
	assert.ok(!second.stdout.includes("would "), second.stdout);
	assert.ok(second.stdout.includes("unchanged Claude plugin: hstack@hstack (version 0.1.0)"));
});

test("auto-update goes to CLAUDE_CONFIG_DIR, and a person's autoUpdate value stays", () => {
	const work = join(home, ".claude-work");
	assert.equal(run([], { CLAUDE_CONFIG_DIR: work }).status, 0);
	assert.equal(settings(work).extraKnownMarketplaces.hstack.autoUpdate, true);
	assert.equal(settings().extraKnownMarketplaces, undefined);
	const chosen = { extraKnownMarketplaces: { hstack: { source: { source: "github", repo: SLUG }, autoUpdate: false } } };
	assert.equal(ensureAutoUpdate(chosen, "hstack", {}), false);
	assert.equal(chosen.extraKnownMarketplaces.hstack.autoUpdate, false);
});

test("a symlinked settings file keeps its link and mode; a new one is created 0600", () => {
	const real = join(root, "dotfiles/settings.json");
	mkdirSync(dirname(real), { recursive: true });
	renameSync(join(home, ".claude/settings.json"), real);
	chmodSync(real, 0o600);
	symlinkSync(real, join(home, ".claude/settings.json"));
	assert.equal(run().status, 0);
	assert.ok(lstatSync(join(home, ".claude/settings.json")).isSymbolicLink());
	assert.equal(JSON.parse(readFileSync(real, "utf8")).extraKnownMarketplaces.hstack.autoUpdate, true);
	assert.equal(statSync(real).mode & 0o777, 0o600);

	const work = join(home, ".claude-new");
	assert.equal(run([], { CLAUDE_CONFIG_DIR: work }).status, 0);
	assert.equal(statSync(join(work, "settings.json")).mode & 0o777, 0o600);
});

test("foreign entries are left alone and reported", () => {
	writeFileSync(join(root, "markets.json"), JSON.stringify([{ name: "hstack", source: "directory", path: "/elsewhere" }]));
	symlinkSync("/elsewhere/plugin", join(home, ".gemini/config/plugins/hstack"));
	const dry = run(["--dry-run"]);
	assert.equal(dry.status, 1);
	assert.ok(dry.stderr.includes("Claude marketplace hstack comes from directory /elsewhere"));
	assert.ok(dry.stdout.includes("Claude plugin hstack@hstack not installed: its marketplace is not ours"));
	assert.ok(dry.stderr.includes("this repo did not create it"));
	rmSync(join(home, ".gemini/config/plugins/hstack"));
	mkdirSync(join(root, "foreign"));
	writeFileSync(join(root, "foreign/plugin.json"), JSON.stringify({ name: "hstack", description: "someone else's hstack" }));
	cpSync(join(root, "foreign"), join(home, ".gemini/config/plugins/hstack"), { recursive: true });
	writeFileSync(join(home, ".claude/settings.json"), "{not json");
	writeFileSync(join(root, "markets.json"), "[]");
	const foreign = run(["--dry-run"]);
	assert.ok(foreign.stderr.includes("holds a plugin this repo did not ship (hstack)"));
	assert.ok(foreign.stderr.includes("settings not valid JSON"));
	assert.ok(!foreign.stdout.includes("agy plugin copy"));
});

test("leftovers of the legacy harness plugin are reported with their removal command, not removed", () => {
	writeFileSync(join(root, "markets.json"), JSON.stringify([{ name: "harness", source: "directory", path: join(home, ".local/state/harness/plugins/claude") }]));
	mkdirSync(join(home, ".gemini/config/plugins/harness"), { recursive: true });
	writeFileSync(
		join(home, ".gemini/config/plugins/harness/plugin.json"),
		JSON.stringify({ name: "harness", description: "Personal harness guardrails: a work-mode merge guard, a read-only reviewer agent, and Antigravity rules." }),
	);
	const result = run();
	assert.equal(result.status, 0, result.stderr);
	assert.ok(result.stdout.includes("legacy Claude marketplace harness"));
	assert.ok(result.stdout.includes("claude plugin marketplace remove harness"));
	assert.ok(result.stdout.includes("agy plugin uninstall harness"));
	assert.ok(existsSync(join(home, ".gemini/config/plugins/harness/plugin.json")));
	assert.ok(!calls().some((c) => c.includes("remove") || c.includes("uninstall")));

	writeFileSync(join(root, "markets.json"), JSON.stringify([{ name: "harness", source: "github", repo: "someone/else" }]));
	assert.ok(!run(["--dry-run"]).stdout.includes("legacy Claude marketplace"), "another owner's harness marketplace is not ours to mention");
});

test("CLIs that are not on PATH are skipped", () => {
	const result = spawnSync(process.execPath, [INSTALL, "--out", out, "--dry-run"], { encoding: "utf8", env: { ...process.env, HOME: home, PATH: "/nonexistent" } });
	assert.equal(result.status, 0);
	assert.ok(result.stdout.includes("claude not on PATH"));
	assert.ok(result.stdout.includes("agy not on PATH"));
});
