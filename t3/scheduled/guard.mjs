#!/usr/bin/env bun
// Guard for T3 scheduled tasks. A T3 scheduled task is an agent turn with no
// timeout, daily run limit, or auto-disable, which herdr-cron enforces for its
// jobs. The guard enforces them from jobs.json so the turn only starts, waits
// for, and reports a supervised run.
import { spawn } from "node:child_process";
import {
	appendFileSync,
	existsSync,
	mkdirSync,
	openSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SELF = fileURLToPath(import.meta.url);
const REPO = resolve(dirname(SELF), "../..");
const KILL_GRACE_MS = 10_000;
const TAIL_CHARS = 4000;

export const EXIT = { ok: 0, failed: 1, disabled: 3, limit: 4, busy: 5, running: 75 };

export function stateRoot(env = process.env) {
	const xdg = env.XDG_STATE_HOME;
	const base = xdg && isAbsolute(xdg) ? xdg : join(homedir(), ".local/state");
	return join(base, "harness-t3-jobs");
}

export function loadJobs(file = join(REPO, "t3/scheduled/jobs.json")) {
	const data = JSON.parse(readFileSync(file, "utf8"));
	if (data.version !== 1 || !Array.isArray(data.jobs)) throw new Error(`${file}: expected version 1 with jobs[]`);
	return data.jobs;
}

export function findJob(jobs, id) {
	const job = jobs.find((j) => j.id === id);
	if (!job) throw new Error(`unknown job: ${id}`);
	for (const key of ["timezone", "timeoutSeconds", "maxRunsPerDay", "failureLimit"])
		if (job[key] === undefined) throw new Error(`job ${id} has no ${key}`);
	if (job.kind === "shell" && (!Array.isArray(job.command) || job.command.length === 0))
		throw new Error(`shell job ${id} has no command`);
	return job;
}

function expand(value, repo) {
	return value.replaceAll("{repo}", repo).replace(/^~(?=\/|$)/, homedir());
}

export function localDay(ms, timezone) {
	return new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(ms));
}

function jobDir(root, id) {
	const dir = join(root, id);
	mkdirSync(dir, { recursive: true, mode: 0o700 });
	return dir;
}

function readRuns(dir) {
	const file = join(dir, "runs.jsonl");
	if (!existsSync(file)) return [];
	return readFileSync(file, "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line));
}

function appendRun(dir, record) {
	appendFileSync(join(dir, "runs.jsonl"), `${JSON.stringify(record)}\n`, { mode: 0o600 });
}

/** Folds the start/end ledger into one entry per run, oldest first. */
export function summarizeRuns(records) {
	const runs = new Map();
	for (const r of records) runs.set(r.run, { ...runs.get(r.run), ...r });
	return [...runs.values()];
}

function alive(pid) {
	if (!pid) return false;
	try {
		process.kill(pid, 0);
		return true;
	} catch {
		return false;
	}
}

function readLock(dir) {
	try {
		return JSON.parse(readFileSync(join(dir, "lock", "owner.json"), "utf8"));
	} catch {
		return null;
	}
}

/** A lock is stale when its supervisor died or an agent run passed its deadline without finishing. */
function lockIsStale(lock, now) {
	if (!lock) return true;
	if (lock.pid) return !alive(lock.pid);
	return now > lock.expiresAt;
}

function release(dir) {
	rmSync(join(dir, "lock"), { recursive: true, force: true });
}

function failureStreak(runs) {
	let streak = 0;
	for (let i = runs.length - 1; i >= 0; i--) {
		const status = runs[i].status;
		if (status === "failed" || status === "timeout" || status === "abandoned") streak++;
		else if (status === "ok" || status === "noop") break;
	}
	return streak;
}

export function recordEnd(dir, job, run, status, extra = {}) {
	appendRun(dir, { run, status, endedAt: Date.now(), ...extra });
	const runs = summarizeRuns(readRuns(dir));
	if (failureStreak(runs) >= job.failureLimit)
		writeFileSync(join(dir, "disabled"), `${JSON.stringify({ at: Date.now(), reason: `${job.failureLimit} consecutive failures`, lastRun: run })}\n`, { mode: 0o600 });
}

/**
 * Admits one run or refuses it. Returns {status, run?}. A stale lock left by a
 * crashed supervisor or an unfinished agent run is closed as `abandoned`, which
 * counts toward the failure streak.
 */
export function admit(job, { root = stateRoot(), now = Date.now(), pid = null } = {}) {
	const dir = jobDir(root, job.id);
	if (existsSync(join(dir, "disabled"))) return { status: "disabled", dir };
	const lockDir = join(dir, "lock");
	const held = existsSync(lockDir) ? readLock(dir) : null;
	if (existsSync(lockDir)) {
		if (!lockIsStale(held, now)) return { status: "busy", dir, run: held?.run };
		if (held?.run && !summarizeRuns(readRuns(dir)).find((r) => r.run === held.run)?.endedAt)
			recordEnd(dir, job, held.run, "abandoned");
		release(dir);
		if (existsSync(join(dir, "disabled"))) return { status: "disabled", dir };
	}
	const today = localDay(now, job.timezone);
	const started = summarizeRuns(readRuns(dir)).filter((r) => localDay(r.startedAt, job.timezone) === today).length;
	if (started >= job.maxRunsPerDay) return { status: "limit", dir };
	try {
		mkdirSync(lockDir, { mode: 0o700 });
	} catch {
		return { status: "busy", dir };
	}
	const run = `${now}-${process.pid}`;
	writeFileSync(join(lockDir, "owner.json"), JSON.stringify({ run, pid, expiresAt: now + job.timeoutSeconds * 1000 }), { mode: 0o600 });
	appendRun(dir, { run, startedAt: now });
	return { status: "admitted", dir, run };
}

function tail(file) {
	if (!existsSync(file)) return "";
	const text = readFileSync(file, "utf8");
	return text.length > TAIL_CHARS ? `...\n${text.slice(-TAIL_CHARS)}` : text;
}

function lastLine(file) {
	const lines = existsSync(file) ? readFileSync(file, "utf8").split("\n").map((l) => l.trim()).filter(Boolean) : [];
	return lines.at(-1) ?? "";
}

function resultLine(job, run, status, exit, log) {
	return `GUARD_RESULT job=${job.id} run=${run ?? "-"} status=${status} exit=${exit ?? "-"}${log ? ` log=${log}` : ""}`;
}

/** Runs inside the detached supervisor: owns the command's process group and its deadline. */
async function supervise(job, run, dir, repo) {
	const log = join(dir, `${run}.log`);
	const out = openSync(log, "a", 0o600);
	const [command, ...args] = job.command.map((part) => expand(part, repo));
	const child = spawn(command, args, { cwd: expand(job.cwd ?? "{repo}", repo), detached: true, stdio: ["ignore", out, out] });
	let timedOut = false;
	const kill = (signal) => {
		try {
			process.kill(-child.pid, signal);
		} catch {}
	};
	const timer = setTimeout(() => {
		timedOut = true;
		kill("SIGTERM");
		setTimeout(() => kill("SIGKILL"), KILL_GRACE_MS).unref();
	}, job.timeoutSeconds * 1000);
	const [code, signal] = await new Promise((done) => {
		child.once("error", (error) => {
			appendFileSync(log, `guard: ${error.message}\n`);
			done([127, null]);
		});
		child.once("close", (c, s) => done([c, s]));
	});
	clearTimeout(timer);
	// The direct child may exit on SIGTERM while a descendant in its group ignores it.
	if (timedOut) kill("SIGKILL");
	let status = timedOut ? "timeout" : code === 0 ? "ok" : "failed";
	if (status === "ok" && job.noOpMarker && lastLine(log) === job.noOpMarker) status = "noop";
	recordEnd(dir, job, run, status, { exit: code, signal });
	writeFileSync(join(dir, `${run}.result.json`), JSON.stringify({ status, exit: code, signal }), { mode: 0o600 });
	release(dir);
}

async function waitFor(job, dir, run, maxSeconds) {
	const resultFile = join(dir, `${run}.result.json`);
	const deadline = Date.now() + maxSeconds * 1000;
	while (!existsSync(resultFile)) {
		if (Date.now() >= deadline) {
			console.log(resultLine(job, run, "running", null, null));
			return EXIT.running;
		}
		await Bun.sleep(1000);
	}
	const { status, exit } = JSON.parse(readFileSync(resultFile, "utf8"));
	const log = join(dir, `${run}.log`);
	const text = tail(log);
	if (text) console.log(text.trimEnd());
	console.log(resultLine(job, run, status, exit, log));
	return status === "ok" || status === "noop" ? EXIT.ok : EXIT.failed;
}

function usage() {
	return [
		"usage: bun t3/scheduled/guard.mjs run <job> [--max-seconds N] [--jobs FILE]",
		"       bun t3/scheduled/guard.mjs wait <job> <run> [--max-seconds N] [--jobs FILE]",
		"       bun t3/scheduled/guard.mjs admit <job> [--jobs FILE]",
		"       bun t3/scheduled/guard.mjs finish <job> <run> --status ok|noop|failed [--jobs FILE]",
		"       bun t3/scheduled/guard.mjs status <job> [--jobs FILE]",
		"",
		"run starts a supervised shell job and waits up to --max-seconds (default 240) for it;",
		`exit ${EXIT.running} means it is still running: call wait with the printed run id.`,
		"admit/finish bracket an agent job. Exit codes: 0 ok/noop, 1 failed/timeout, 3 disabled, 4 daily limit, 5 busy.",
		"A disabled job stays disabled until a person deletes <state>/<job>/disabled.",
	].join("\n");
}

function option(argv, name, fallback) {
	const i = argv.indexOf(name);
	if (i === -1) return fallback;
	const value = argv[i + 1];
	if (value === undefined || value.startsWith("--")) throw new Error(`${name} requires a value`);
	argv.splice(i, 2);
	return value;
}

export async function main(argv = process.argv.slice(2)) {
	argv = [...argv];
	const jobsFile = option(argv, "--jobs", undefined);
	const maxSeconds = Number(option(argv, "--max-seconds", "240"));
	const status = option(argv, "--status", undefined);
	const [action, id, run] = argv;
	if (!action || action === "--help" || action === "-h") {
		console.log(usage());
		return action ? 0 : 2;
	}
	const job = findJob(loadJobs(jobsFile), id);
	const root = stateRoot();
	if (action === "_supervise") {
		await supervise(job, run, jobDir(root, job.id), REPO);
		return 0;
	}
	if (action === "run") {
		if (job.kind !== "shell") throw new Error(`${id} is an ${job.kind} job; use admit/finish`);
		const admitted = admit(job, { root });
		if (admitted.status !== "admitted") {
			console.log(resultLine(job, admitted.run, admitted.status, null, null));
			return EXIT[admitted.status];
		}
		const supervisor = spawn(process.execPath, [SELF, "_supervise", id, admitted.run, ...(jobsFile ? ["--jobs", jobsFile] : [])], { detached: true, stdio: "ignore" });
		supervisor.unref();
		const owner = join(admitted.dir, "lock", "owner.json");
		writeFileSync(owner, JSON.stringify({ ...JSON.parse(readFileSync(owner, "utf8")), pid: supervisor.pid }), { mode: 0o600 });
		return waitFor(job, admitted.dir, admitted.run, maxSeconds);
	}
	if (action === "wait") {
		if (!run) throw new Error("wait needs a run id");
		return waitFor(job, jobDir(root, job.id), run, maxSeconds);
	}
	if (action === "admit") {
		if (job.kind !== "agent") throw new Error(`${id} is a ${job.kind} job; use run`);
		const admitted = admit(job, { root });
		console.log(resultLine(job, admitted.run, admitted.status, null, null));
		return admitted.status === "admitted" ? EXIT.ok : EXIT[admitted.status];
	}
	if (action === "finish") {
		if (!run || !["ok", "noop", "failed"].includes(status)) throw new Error("finish needs <run> and --status ok|noop|failed");
		const dir = jobDir(root, job.id);
		if (readLock(dir)?.run !== run) throw new Error(`run ${run} does not hold the ${id} lock`);
		recordEnd(dir, job, run, status);
		release(dir);
		console.log(resultLine(job, run, status, null, null));
		return EXIT.ok;
	}
	if (action === "status") {
		const dir = jobDir(root, job.id);
		const runs = summarizeRuns(readRuns(dir));
		const disabled = existsSync(join(dir, "disabled")) ? JSON.parse(readFileSync(join(dir, "disabled"), "utf8")) : null;
		console.log(JSON.stringify({ job: id, disabled, lock: readLock(dir), recent: runs.slice(-5) }, null, 2));
		return EXIT.ok;
	}
	throw new Error(`unknown action: ${action}\n${usage()}`);
}

if (import.meta.main) {
	main().then(
		(code) => {
			process.exitCode = code;
		},
		(error) => {
			console.error(error.message);
			process.exitCode = 2;
		},
	);
}
