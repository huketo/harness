// Contract tests for t3/scheduled/guard.mjs. Every case uses a temporary
// jobs file and XDG_STATE_HOME; nothing reads the real state or runs a job.
import { afterEach, beforeEach, expect, test } from "bun:test";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { admit, loadJobs } from "./guard.mjs";

const GUARD = join(import.meta.dir, "guard.mjs");
let root;
let jobsFile;

function job(id, fields) {
	return { id, kind: "shell", cwd: root, timezone: "Asia/Seoul", timeoutSeconds: 30, maxRunsPerDay: 10, failureLimit: 3, ...fields };
}

function writeJobs(...jobs) {
	writeFileSync(jobsFile, JSON.stringify({ version: 1, jobs }));
}

function guard(...args) {
	const child = Bun.spawnSync([process.execPath, GUARD, ...args, "--jobs", jobsFile], {
		env: { ...process.env, XDG_STATE_HOME: join(root, "state") },
	});
	return { code: child.exitCode, out: child.stdout.toString(), err: child.stderr.toString() };
}

function result(out) {
	const line = out.trim().split("\n").at(-1);
	return Object.fromEntries(line.replace(/^GUARD_RESULT /, "").split(" ").map((kv) => kv.split("=")));
}

beforeEach(() => {
	root = mkdtempSync(join(tmpdir(), "t3-guard-test-"));
	jobsFile = join(root, "jobs.json");
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

test("a successful run reports its output tail and status ok", () => {
	writeJobs(job("hello", { command: ["sh", "-c", "echo collected; echo done"] }));
	const run = guard("run", "hello");
	expect(run.code).toBe(0);
	expect(run.out).toContain("collected");
	expect(result(run.out)).toMatchObject({ job: "hello", status: "ok", exit: "0" });
});

test("a run past its deadline is killed with its whole process group", () => {
	const marker = join(root, "grandchild-survived");
	writeJobs(job("slow", { timeoutSeconds: 1, command: ["sh", "-c", `(sleep 3; touch ${marker}) & sleep 30`] }));
	const run = guard("run", "slow", "--max-seconds", "20");
	expect(run.code).toBe(1);
	expect(result(run.out).status).toBe("timeout");
	Bun.sleepSync(3500);
	expect(existsSync(marker)).toBe(false);
}, 30_000);

test("the daily limit refuses a run before starting it", () => {
	writeJobs(job("once", { maxRunsPerDay: 1, command: ["true"] }));
	expect(guard("run", "once").code).toBe(0);
	const second = guard("run", "once");
	expect(second.code).toBe(4);
	expect(result(second.out).status).toBe("limit");
});

test("consecutive failures disable the job until a person removes the marker", () => {
	writeJobs(job("flaky", { failureLimit: 2, command: ["false"] }));
	expect(guard("run", "flaky").code).toBe(1);
	expect(guard("run", "flaky").code).toBe(1);
	const third = guard("run", "flaky");
	expect(third.code).toBe(3);
	expect(result(third.out).status).toBe("disabled");
	rmSync(join(root, "state/harness-t3-jobs/flaky/disabled"));
	expect(result(guard("run", "flaky").out).status).toBe("failed");
});

test("a success between failures resets the streak", () => {
	const flag = join(root, "fail");
	writeJobs(job("mixed", { failureLimit: 2, command: ["sh", "-c", `test ! -e ${flag}`] }));
	writeFileSync(flag, "");
	expect(guard("run", "mixed").code).toBe(1);
	rmSync(flag);
	expect(guard("run", "mixed").code).toBe(0);
	writeFileSync(flag, "");
	expect(result(guard("run", "mixed").out).status).toBe("failed");
	expect(result(guard("run", "mixed").out).status).toBe("failed");
	expect(result(guard("run", "mixed").out).status).toBe("disabled");
});

test("the job's no-op marker as the last output line reports noop", () => {
	writeJobs(job("idle", { noOpMarker: "NO_USAGE_DATA", command: ["sh", "-c", "echo NO_USAGE_DATA"] }));
	const run = guard("run", "idle");
	expect(run.code).toBe(0);
	expect(result(run.out).status).toBe("noop");
});

test("a long run returns 75 with its run id and wait collects the result", () => {
	writeJobs(job("long", { command: ["sh", "-c", "sleep 2; echo finished"] }));
	const first = guard("run", "long", "--max-seconds", "0");
	expect(first.code).toBe(75);
	const { run, status } = result(first.out);
	expect(status).toBe("running");
	expect(guard("run", "long").code).toBe(5);
	const done = guard("wait", "long", run, "--max-seconds", "20");
	expect(done.code).toBe(0);
	expect(done.out).toContain("finished");
	expect(result(done.out)).toMatchObject({ run, status: "ok" });
}, 30_000);

test("an agent job is bracketed by admit and finish and is busy in between", () => {
	writeJobs(job("sync", { kind: "agent" }));
	const admitted = guard("admit", "sync");
	expect(admitted.code).toBe(0);
	const { run } = result(admitted.out);
	expect(guard("admit", "sync").code).toBe(5);
	expect(guard("finish", "sync", "other-run", "--status", "ok").code).toBe(2);
	expect(guard("finish", "sync", run, "--status", "noop").code).toBe(0);
	expect(guard("admit", "sync").code).toBe(0);
});

test("an agent run that never finishes is closed as abandoned after its deadline", () => {
	const sync = job("sync", { kind: "agent", timeoutSeconds: 60, failureLimit: 1 });
	writeJobs(sync);
	const state = join(root, "state/harness-t3-jobs");
	const start = Date.UTC(2026, 9, 26, 12, 0, 0);
	expect(admit(sync, { root: state, now: start }).status).toBe("admitted");
	expect(admit(sync, { root: state, now: start + 30_000 }).status).toBe("busy");
	expect(admit(sync, { root: state, now: start + 61_000 }).status).toBe("disabled");
	const ledger = readFileSync(join(state, "sync/runs.jsonl"), "utf8");
	expect(ledger).toContain('"status":"abandoned"');
});

test("the tracked jobs file is the empty public snapshot", () => {
	expect(loadJobs()).toEqual([]);
});
