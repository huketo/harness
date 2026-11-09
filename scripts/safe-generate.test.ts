import assert from "node:assert/strict";
import { chmodSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, readlinkSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { applyPlan, facts, findRulesync, generate, homeRelative, realPath, reconcile, renderSource, restoreArrays } from "./safe-generate.ts";

const REPO = dirname(dirname(fileURLToPath(import.meta.url)));
const temps: string[] = [];
after(() => temps.forEach((dir) => rmSync(dir, { recursive: true, force: true })));

function tempHome(): string {
	const dir = mkdtempSync(join(tmpdir(), "hstack-sg-"));
	temps.push(dir);
	return dir;
}

function put(path: string, value: unknown) {
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, typeof value === "string" ? value : JSON.stringify(value));
}

test("Claude files map to the config directory, everything else to HOME", () => {
	assert.equal(realPath(".claude/settings.json", "/h", "/h/.claude-work"), "/h/.claude-work/settings.json");
	assert.equal(realPath(".gemini/antigravity-cli/settings.json", "/h", "/h/.claude"), "/h/.gemini/antigravity-cli/settings.json");
});

test("templates fill the Claude config directory and drop a line that became a duplicate", () => {
	assert.equal(homeRelative("/h/.claude-work", "/h"), "~/.claude-work");
	assert.equal(homeRelative("/elsewhere/claude", "/h"), "/elsewhere/claude");
	const source = '  "~/.claude/.credentials.json": "deny",\n  "{{CLAUDE_CONFIG_DIR}}/.credentials.json": "deny",\n';
	assert.equal(renderSource(source, { home: "/h", claudeDir: "/h/.claude" }), '  "~/.claude/.credentials.json": "deny",\n');
	assert.match(renderSource(source, { home: "/h", claudeDir: "/h/.claude-work" }), /~\/\.claude-work\/\.credentials\.json/);
});

test("array items a generator dropped are put back after its own items; scalars are not", () => {
	const prev = { model: "a", permissions: { deny: ["Read(./x)", "Read(~/.ssh/**)"], allow: ["Bash(ls:*)"] } };
	const next: any = { model: "b", permissions: { deny: ["Read(~/.ssh/**)", "Read(~/.aws/**)"] } };
	assert.deepEqual(restoreArrays(prev, next), ['permissions.deny[]="Read(./x)"', 'permissions.allow[]="Bash(ls:*)"']);
	assert.deepEqual(next.permissions.deny, ["Read(~/.ssh/**)", "Read(~/.aws/**)", "Read(./x)"]);
	assert.equal(next.model, "b");
});

test("reconcile keeps existing entries and reports a changed scalar as a loss", () => {
	const kept = reconcile(JSON.stringify({ permissions: { deny: ["A"] } }), JSON.stringify({ permissions: { deny: ["B"] } }));
	assert.deepEqual(kept.restored, ['permissions.deny[]="A"']);
	assert.deepEqual(kept.lost, []);
	assert.deepEqual(JSON.parse(kept.next).permissions.deny, ["B", "A"]);
	const changed = reconcile(JSON.stringify({ model: "a" }), JSON.stringify({ model: "b" }));
	assert.deepEqual(changed.lost, ['model="a"']);
	const text = reconcile("keep\nold\n", "keep\nnew\n");
	assert.deepEqual(text.lost, ["old"]);
	assert.ok(facts({ a: [1, { b: 2 }] }).has('a[]={"b":2}'));
});

test("applyPlan refuses a lossy plan and backs up what it replaces", () => {
	const home = tempHome();
	const file = join(home, "settings.json");
	put(file, "{}");
	assert.throws(() => applyPlan({ files: [{ target: file, prev: "{}", next: "{}", added: [], restored: [], lost: ["x"] }], log: [], skipped: [] }));
	applyPlan({ files: [{ target: file, prev: "{}", next: '{"a":1}\n', added: ["a=1"], restored: [], lost: [] }], log: [], skipped: [] }, "STAMP");
	assert.equal(readFileSync(file, "utf8"), '{"a":1}\n');
	assert.equal(readFileSync(`${file}.hstack-bak-STAMP`, "utf8"), "{}");
});

test("applyPlan writes through a symlinked settings file, keeps its mode, and refuses a file changed since the plan", () => {
	const home = tempHome();
	const real = join(home, "dotfiles/settings.json");
	const link = join(home, "settings.json");
	put(real, "{}");
	chmodSync(real, 0o600);
	symlinkSync(real, link);
	applyPlan({ files: [{ target: link, prev: "{}", next: '{"a":1}\n', added: ["a=1"], restored: [], lost: [] }], log: [], skipped: [] }, "S1");
	assert.ok(lstatSync(link).isSymbolicLink(), "the link survives");
	assert.equal(readlinkSync(link), real);
	assert.equal(readFileSync(real, "utf8"), '{"a":1}\n');
	assert.equal(statSync(real).mode & 0o777, 0o600);
	assert.equal(readFileSync(`${real}.hstack-bak-S1`, "utf8"), "{}");

	writeFileSync(real, '{"model":"newer"}');
	assert.throws(() => applyPlan({ files: [{ target: link, prev: '{"a":1}\n', next: '{"a":2}\n', added: [], restored: [], lost: [] }], log: [], skipped: [] }), /changed since/);
	assert.equal(readFileSync(real, "utf8"), '{"model":"newer"}');

	const fresh = join(home, "new/settings.json");
	applyPlan({ files: [{ target: fresh, prev: null, next: "{}\n", added: [], restored: [], lost: [] }], log: [], skipped: [] });
	assert.equal(statSync(fresh).mode & 0o777, 0o600);
});

const rulesync = findRulesync(REPO);

test("rulesync run: adds the denies, keeps foreign entries, honors CLAUDE_CONFIG_DIR, and is idempotent", { skip: rulesync ? false : "rulesync not installed (mise install)" }, () => {
	const home = tempHome();
	const claudeDir = join(home, ".claude-work");
	put(join(claudeDir, "settings.json"), { model: "opus", permissions: { allow: ["Bash(ls:*)"], deny: ["Read(./secret.txt)", "Bash(rm -rf:*)"] } });
	put(join(home, ".gemini/antigravity-cli/settings.json"), { permissions: { deny: ["command(sudo)", "read_file(/elsewhere/token)"] } });

	const plan = generate({ repo: REPO, home, claudeDir, rulesync: rulesync! });
	assert.deepEqual(plan.skipped, []);
	assert.deepEqual(plan.files.map((f) => f.target).sort(), [join(claudeDir, "settings.json"), join(home, ".gemini/antigravity-cli/settings.json")]);
	assert.ok(plan.files.every((f) => f.lost.length === 0));
	applyPlan(plan);

	const claude = JSON.parse(readFileSync(join(claudeDir, "settings.json"), "utf8"));
	assert.equal(claude.model, "opus");
	assert.deepEqual(claude.permissions.allow, ["Bash(ls:*)"]);
	for (const rule of ["Read(./secret.txt)", "Bash(rm -rf:*)", "Read(~/.ssh/**)", "Read(~/.claude/.credentials.json)", "Read(~/.claude-work/.credentials.json)"])
		assert.ok(claude.permissions.deny.includes(rule), rule);
	const agy = JSON.parse(readFileSync(join(home, ".gemini/antigravity-cli/settings.json"), "utf8"));
	for (const rule of ["command(sudo)", "read_file(/elsewhere/token)", `read_file(${home}/.ssh)`]) assert.ok(agy.permissions.deny.includes(rule), rule);
	assert.ok(!JSON.stringify(agy).includes("hstack-generate-"), "no staging path leaks into agy paths");
	assert.ok(!readdirSync(home).includes(".claude"), "nothing is written under ~/.claude when CLAUDE_CONFIG_DIR points elsewhere");

	assert.deepEqual(generate({ repo: REPO, home, claudeDir, rulesync: rulesync! }).files, []);
});

test("rulesync run: an agent that is not installed is skipped, not created", { skip: rulesync ? false : "rulesync not installed (mise install)" }, () => {
	const home = tempHome();
	const plan = generate({ repo: REPO, home, claudeDir: join(home, ".claude"), rulesync: rulesync! });
	assert.deepEqual(plan, { files: [], log: [], skipped: ["claudecode", "antigravity-cli"] });
});
