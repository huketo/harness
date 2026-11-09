// Contract tests for t3/scheduled/guard.mjs. Every case uses a temporary
// jobs file and XDG_STATE_HOME; nothing reads the real state or runs a job.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { admit, loadJobs } from "./guard.mjs";

const GUARD = join(import.meta.dirname, "guard.mjs");
let root;
let jobsFile;

function job(id, fields) {
	return { id, kind: "shell", cwd: root, timezone: "Asia/Seoul", timeoutSeconds: 30, maxRunsPerDay: 10, failureLimit: 3, ...fields };
}

function writeJobs(...jobs) {
	writeFileSync(jobsFile, JSON.stringify({ version: 1, jobs }));
}

function guard(...args) {
	const child = spawnSync(process.execPath, [GUARD, ...args, "--jobs", jobsFile], {
		env: { ...process.env, XDG_STATE_HOME: join(root, "state") },
		stdio: ["ignore", "pipe", "pipe"],
	});
	return { code: child.status, out: child.stdout.toString(), err: child.stderr.toString() };
}

function result(out) {
	const line = out.trim().split("\n").at(-1);
	return Object.fromEntries(line.replace(/^GUARD_RESULT /, "").split(" ").map((kv) => kv.split("=")));
}

function sleepSync(ms) {
	Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

beforeEach(() => {
	root = mkdtempSync(join(tmpdir(), "t3-guard-test-"));
	jobsFile = join(root, "jobs.json");
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

test("a successful run reports its output tail and status ok", () => {
	writeJobs(job("hello", { command: ["sh", "-c", "echo collected; echo done"] }));
	const run = guard("run", "hello");
	assert.equal(run.code, 0);
	assert.ok(run.out.includes("collected"));
	const fields = result(run.out);
	assert.equal(fields.job, "hello");
	assert.equal(fields.status, "ok");
	assert.equal(fields.exit, "0");
});

test("a run past its deadline is killed with its whole process group", { timeout: 30_000 }, () => {
	const marker = join(root, "grandchild-survived");
	writeJobs(job("slow", { timeoutSeconds: 1, command: ["sh", "-c", `(sleep 3; touch ${marker}) & sleep 30`] }));
	const run = guard("run", "slow", "--max-seconds", "20");
	assert.equal(run.code, 1);
	assert.equal(result(run.out).status, "timeout");
	sleepSync(3500);
	assert.equal(existsSync(marker), false);
});

test("the daily limit refuses a run before starting it", () => {
	writeJobs(job("once", { maxRunsPerDay: 1, command: ["true"] }));
	assert.equal(guard("run", "once").code, 0);
	const second = guard("run", "once");
	assert.equal(second.code, 4);
	assert.equal(result(second.out).status, "limit");
});

test("consecutive failures disable the job until a person removes the marker", () => {
	writeJobs(job("flaky", { failureLimit: 2, command: ["false"] }));
	assert.equal(guard("run", "flaky").code, 1);
	assert.equal(guard("run", "flaky").code, 1);
	const third = guard("run", "flaky");
	assert.equal(third.code, 3);
	assert.equal(result(third.out).status, "disabled");
	rmSync(join(root, "state/harness-t3-jobs/flaky/disabled"));
	assert.equal(result(guard("run", "flaky").out).status, "failed");
});

test("a success between failures resets the streak", () => {
	const flag = join(root, "fail");
	writeJobs(job("mixed", { failureLimit: 2, command: ["sh", "-c", `test ! -e ${flag}`] }));
	writeFileSync(flag, "");
	assert.equal(guard("run", "mixed").code, 1);
	rmSync(flag);
	assert.equal(guard("run", "mixed").code, 0);
	writeFileSync(flag, "");
	assert.equal(result(guard("run", "mixed").out).status, "failed");
	assert.equal(result(guard("run", "mixed").out).status, "failed");
	assert.equal(result(guard("run", "mixed").out).status, "disabled");
});

test("the job's no-op marker as the last output line reports noop", () => {
	writeJobs(job("idle", { noOpMarker: "NO_USAGE_DATA", command: ["sh", "-c", "echo NO_USAGE_DATA"] }));
	const run = guard("run", "idle");
	assert.equal(run.code, 0);
	assert.equal(result(run.out).status, "noop");
});

test("a long run returns 75 with its run id and wait collects the result", { timeout: 30_000 }, () => {
	writeJobs(job("long", { command: ["sh", "-c", "sleep 2; echo finished"] }));
	const first = guard("run", "long", "--max-seconds", "0");
	assert.equal(first.code, 75);
	const { run, status } = result(first.out);
	assert.equal(status, "running");
	assert.equal(guard("run", "long").code, 5);
	const done = guard("wait", "long", run, "--max-seconds", "20");
	assert.equal(done.code, 0);
	assert.ok(done.out.includes("finished"));
	const fields = result(done.out);
	assert.equal(fields.run, run);
	assert.equal(fields.status, "ok");
});

test("an agent job is bracketed by admit and finish and is busy in between", () => {
	writeJobs(job("sync", { kind: "agent" }));
	const admitted = guard("admit", "sync");
	assert.equal(admitted.code, 0);
	const { run } = result(admitted.out);
	assert.equal(guard("admit", "sync").code, 5);
	assert.equal(guard("finish", "sync", "other-run", "--status", "ok").code, 2);
	assert.equal(guard("finish", "sync", run, "--status", "noop").code, 0);
	assert.equal(guard("admit", "sync").code, 0);
});

test("an agent run that never finishes is closed as abandoned after its deadline", () => {
	const sync = job("sync", { kind: "agent", timeoutSeconds: 60, failureLimit: 1 });
	writeJobs(sync);
	const state = join(root, "state/harness-t3-jobs");
	const start = Date.UTC(2026, 9, 26, 12, 0, 0);
	assert.equal(admit(sync, { root: state, now: start }).status, "admitted");
	assert.equal(admit(sync, { root: state, now: start + 30_000 }).status, "busy");
	assert.equal(admit(sync, { root: state, now: start + 61_000 }).status, "disabled");
	const ledger = readFileSync(join(state, "sync/runs.jsonl"), "utf8");
	assert.ok(ledger.includes('"status":"abandoned"'));
});

test("the tracked jobs file is the empty public snapshot", () => {
	assert.deepEqual(loadJobs(), []);
});

test("a monthly job is refused outside its days without consuming a run", () => {
	const monthly = job("monthly", { kind: "agent", daysOfMonth: [1, 2, 3] });
	const state = join(root, "state");
	const offDay = Date.parse("2026-11-04T09:00:00+09:00");
	assert.equal(admit(monthly, { root: state, now: offDay }).status, "off_day");
	assert.equal(existsSync(join(state, "monthly", "runs.jsonl")), false);
	assert.equal(admit(monthly, { root: state, now: Date.parse("2026-11-03T09:00:00+09:00") }).status, "admitted");
});

test("a monthly job that already succeeded this month is done until next month", () => {
	const monthly = job("monthly", { kind: "agent", daysOfMonth: [1, 2, 3], maxRunsPerDay: 5 });
	const state = join(root, "state");
	const dir = join(state, "monthly");
	const first = Date.parse("2026-11-01T09:00:00+09:00");
	const ledger = (records) => {
		mkdirSync(dir, { recursive: true });
		rmSync(join(dir, "lock"), { recursive: true, force: true });
		writeFileSync(join(dir, "runs.jsonl"), records.map((r) => `${JSON.stringify(r)}\n`).join(""));
	};
	ledger([{ run: "a", startedAt: first, status: "noop", endedAt: first + 1 }]);
	assert.equal(admit(monthly, { root: state, now: first + 86_400_000 }).status, "admitted");
	ledger([{ run: "b", startedAt: first, status: "ok", endedAt: first + 1 }]);
	assert.equal(admit(monthly, { root: state, now: first + 86_400_000 }).status, "done");
	assert.equal(admit(monthly, { root: state, now: Date.parse("2026-12-01T09:00:00+09:00") }).status, "admitted");
});
