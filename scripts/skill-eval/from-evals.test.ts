import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, test } from "node:test";
import { main as fromEvals } from "./from-evals.ts";
import { validateEvals } from "./lib/evals.ts";
import { listFiles } from "./lib/run/files.ts";
import { main as run } from "./lib/run/runner.ts";
import { loadSuite, validateSuite } from "./lib/schema.ts";

const roots: string[] = [];
after(() => {
	for (const root of roots) rmSync(root, { recursive: true, force: true });
});

function repoWith(files: Record<string, string>): string {
	const repo = mkdtempSync(join(tmpdir(), "from-evals-"));
	roots.push(repo);
	for (const [path, text] of Object.entries(files)) {
		mkdirSync(dirname(join(repo, path)), { recursive: true });
		writeFileSync(join(repo, path), text);
	}
	const git = (...args: string[]) => {
		const result = spawnSync("git", ["-c", "user.name=t", "-c", "user.email=t@t", ...args], { cwd: repo });
		if (result.status !== 0) throw new Error(`git ${args.join(" ")}: ${result.stderr}`);
	};
	git("init", "-q", "-b", "main");
	git("add", ".");
	git("commit", "-qm", "v1");
	return repo;
}

const project = { id: 1, name: "with-project", prompt: "Fix the bug in src/a.ts.", expected_output: "The bug is fixed and shown fixed.", files: ["fixtures/app/src/a.ts", "fixtures/app/README.md"], root: "fixtures/app", expectations: ["Runs the test."] };
const listed = { id: 2, name: "as-listed", prompt: "Polish fixtures/draft.md.", expected_output: "Polished.", files: ["fixtures/draft.md"], expectations: ["Keeps the facts."] };
const routine = { id: 3, name: "routine", prompt: "Rename a variable.", expected_output: "Renamed without ceremony.", files: [], expectations: ["Adds no process."], timeout_sec: 60 };
const tree = {
	"skills/demo/SKILL.md": "# demo\n",
	"skills/demo/evals/fixtures/app/src/a.ts": "export const a = 1;\n",
	"skills/demo/evals/fixtures/app/README.md": "app\n",
	"skills/demo/evals/fixtures/draft.md": "draft\n",
};
const evals = (...cases: object[]) => JSON.stringify({ skill_name: "demo", evals: cases });

function convert(repo: string, ...args: string[]): { code: number; lines: string[] } {
	const lines: string[] = [];
	const code = fromEvals(["--skill", "skills/demo", ...args], { repoRoot: repo, cwd: repo, log: (line) => lines.push(line), warn: (line) => lines.push(line) });
	return { code, lines };
}

test("writes a suite the runner plans: each case without the skill, with it, and with the earlier version", async () => {
	const repo = repoWith({ ...tree, "skills/demo/evals/evals.json": evals(project, listed, routine) });
	const { code, lines } = convert(repo, "--previous", "HEAD");
	assert.equal(code, 0, lines.join("\n"));
	const out = join(repo, "var/skill-eval/suites/demo");
	// `root` becomes the workspace root; without it the paths arrive as the prompt names them.
	assert.deepEqual(listFiles(out), ["fixtures/as-listed/fixtures/draft.md", "fixtures/with-project/README.md", "fixtures/with-project/src/a.ts", "suite.json"]);
	const suiteFile = join(out, "suite.json");
	const suite = loadSuite(suiteFile);
	assert.deepEqual(validateSuite(suite, suiteFile), []);
	assert.deepEqual(Object.keys(suite.arms), ["none", "skill", "previous"]);
	assert.deepEqual(suite.cases.map((c) => [c.id, c.fixture, c.rubric, c.timeoutSec]), [
		["with-project", "with-project", ["The bug is fixed and shown fixed."], undefined],
		["as-listed", "as-listed", ["Polished."], undefined],
		["routine", null, ["Renamed without ceremony."], 60],
	]);

	const plan: string[] = [];
	const planned = await run(["--suite", suiteFile, "--dry-run"], { repoRoot: repo, cwd: repo, log: (line) => plan.push(line), warn: (line) => plan.push(line) });
	assert.equal(planned, 0, plan.join("\n"));
	assert.equal(plan.at(-1), "9 to run, 0 to skip");
});

test("refuses cases the runner could not execute and writes nothing", () => {
	const repo = repoWith({ ...tree, "skills/demo/evals/evals.json": JSON.stringify({ skill_name: "other", evals: [routine] }) });
	const { code, lines } = convert(repo);
	assert.equal(code, 1);
	assert.match(lines.join("\n"), /skill_name must equal the skill directory name "demo"/);
	assert.equal(existsSync(join(repo, "var")), false);
});

test("refuses a skill outside the checkout whose runner would execute it", () => {
	const repo = repoWith({ ...tree, "skills/demo/evals/evals.json": evals(routine) });
	const lines: string[] = [];
	const other = repoWith({ "skills/.keep": "" });
	const code = fromEvals(["--skill", "skills/demo"], { repoRoot: other, cwd: repo, log: (line) => lines.push(line), warn: (line) => lines.push(line) });
	assert.equal(code, 1);
	assert.match(lines.join("\n"), /skills of its own checkout only/);
});

test("a case lists plain files inside an existing root, reached through no symbolic link, and its limit is a whole number the runner accepts", () => {
	const repo = repoWith({ ...tree, "skills/demo/evals/evals.json": "{}", "outside.md": "outside\n" });
	const skillDir = join(repo, "skills/demo");
	symlinkSync(join(repo, "outside.md"), join(skillDir, "evals/fixtures/app/linked.md"));
	symlinkSync(repo, join(skillDir, "evals/fixtures/up"));
	const problems = (patch: object) => validateEvals({ skill_name: "demo", evals: [{ ...routine, ...patch }] }, skillDir);
	assert.deepEqual(problems({ files: ["fixtures/draft.md"], root: "fixtures/app" }), ['evals[0]: file "fixtures/draft.md" must be inside root "fixtures/app"']);
	assert.deepEqual(problems({ files: ["fixtures/app/README.md"], root: "fixtures/app/" }), []);
	for (const root of ["../..", "fixtures/draft.md", "fixtures/draft.md/child", "fixtures/absent", "fixtures/up"]) assert.match(problems({ files: [], root })[0] ?? "", /root must be an existing directory/);
	for (const file of ["fixtures/app", "fixtures/app/linked.md", "fixtures/up/outside.md", "fixtures/absent.md", "fixtures/draft.md/", "fixtures/draft.md/child"]) assert.match(problems({ files: [file] })[0] ?? "", /must be an existing plain file/);
	for (const timeout_sec of [0, 1.5, 3601, JSON.parse("1e400")]) assert.match(problems({ timeout_sec })[0] ?? "", /timeout_sec must be a whole number/);

	const linked = repoWith({ "skills/demo/SKILL.md": "# demo\n", "elsewhere/fixtures/draft.md": "draft\n" });
	symlinkSync(join(linked, "elsewhere"), join(linked, "skills/demo/evals"));
	assert.match(validateEvals({ skill_name: "demo", evals: [listed] }, join(linked, "skills/demo"))[0] ?? "", /root must be an existing directory/);
});

test("refuses a skill directory that is a link out of the checkout", () => {
	const repo = repoWith({ "skills/.keep": "", "elsewhere/demo/SKILL.md": "# demo\n", "elsewhere/demo/evals/evals.json": evals(routine) });
	symlinkSync(join(repo, "elsewhere/demo"), join(repo, "skills/demo"));
	const { code, lines } = convert(repo);
	assert.equal(code, 1);
	assert.match(lines.join("\n"), /skills of its own checkout only/);
});

test("refuses a checkout whose skills directory is a link, and writes the checkout's own path for an alias that reaches a real skill", () => {
	const repo = repoWith({ "elsewhere/demo/SKILL.md": "# demo\n", "elsewhere/demo/evals/evals.json": evals(routine) });
	symlinkSync(join(repo, "elsewhere"), join(repo, "skills"));
	assert.equal(convert(repo).code, 1);

	const real = repoWith({ ...tree, "skills/demo/evals/evals.json": evals(routine) });
	symlinkSync(join(real, "skills"), join(real, "alias"));
	const lines: string[] = [];
	const viaAlias = fromEvals(["--skill", "alias/demo"], { repoRoot: real, cwd: real, log: (line) => lines.push(line), warn: (line) => lines.push(line) });
	assert.equal(viaAlias, 0, lines.join("\n"));
	assert.deepEqual(loadSuite(join(real, "var/skill-eval/suites/demo/suite.json")).arms.skill?.skills, [{ source: "local", path: "skills/demo" }]);
});
