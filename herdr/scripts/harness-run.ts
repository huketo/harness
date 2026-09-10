#!/usr/bin/env bun
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
	mkdir,
	open,
	readdir,
	readFile,
	realpath,
	rename,
	unlink,
	writeFile,
} from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { parseArgs } from "node:util";

export const AGENT_NAME_RE = /^[a-z][a-z0-9_-]{0,31}$/;
export function shellQuote(value: string): string {
	return `'${value.replaceAll("'", "'\\''")}'`;
}
const root = resolve(dirname(await realpath(import.meta.path)), "../..");
const xdg = process.env.XDG_STATE_HOME;
const stateRoot = join(
	xdg && isAbsolute(xdg) ? xdg : join(homedir(), ".local/state"),
	"harness-run",
);

type RecordState = {
	version: 1;
	name: string;
	kind: "command" | "agent";
	cwd: string;
	paneId: string;
	tabId: string;
	profile?: string;
	runner?: "omp" | "agy";
	session?: string;
	runDir?: string;
	marker?: string;
	unattended?: boolean;
	launchError?: string;
	detached?: boolean;
	ownTab?: boolean;
};
function object(value: unknown): Record<string, unknown> {
	if (!value || typeof value !== "object" || Array.isArray(value))
		throw new Error("Expected a JSON object");
	return value as Record<string, unknown>;
}
function text(value: unknown): string {
	if (typeof value !== "string" || !value)
		throw new Error("Expected a nonempty string in CLI response");
	return value;
}
async function logTail(path: string, limit = 65536) {
	const file = await open(path, "r");
	try {
		const { size } = await file.stat();
		const buffer = Buffer.allocUnsafe(Math.min(size, limit));
		const { bytesRead } = await file.read(
			buffer,
			0,
			buffer.length,
			Math.max(0, size - limit),
		);
		return {
			output: buffer.subarray(0, bytesRead).toString("utf8"),
			outputTruncated: size > limit,
		};
	} finally {
		await file.close();
	}
}
export function parseAgyResult(output: string): Record<string, unknown> {
	let result: Record<string, unknown> | undefined;
	for (const line of output.split(/\r?\n/)) {
		let value: unknown;
		try {
			value = JSON.parse(line);
		} catch {
			continue;
		}
		if (value && typeof value === "object" && !Array.isArray(value)) {
			const row = value as Record<string, unknown>;
			if (typeof row.status === "string" && typeof row.response === "string")
				result = row;
		}
	}
	if (result?.status !== "SUCCESS" || !String(result.response).trim())
		throw new Error(
			"AGY result missing or unsuccessful; inspect the retained output.log",
		);
	return result;
}
async function execute(argv: string[], cwd?: string): Promise<string> {
	const { promise, resolve: done, reject } = Promise.withResolvers<string>();
	const child = spawn(argv[0], argv.slice(1), {
		cwd,
		stdio: ["ignore", "pipe", "pipe"],
	});
	let stdout = "",
		stderr = "";
	child.stdout.setEncoding("utf8");
	child.stderr.setEncoding("utf8");
	child.stdout.on("data", (chunk) => {
		stdout += chunk;
	});
	child.stderr.on("data", (chunk) => {
		stderr += chunk;
	});
	const stop = () => child.kill("SIGTERM");
	process.once("SIGTERM", stop);
	process.once("SIGINT", stop);
	child.once("error", (error) => {
		process.off("SIGTERM", stop);
		process.off("SIGINT", stop);
		reject(error);
	});
	child.once("close", (code) => {
		process.off("SIGTERM", stop);
		process.off("SIGINT", stop);
		if (code !== 0)
			reject(
				new Error(`${argv[0]} exited ${code}: ${(stderr || stdout).trim()}`),
			);
		else done(stdout);
	});
	return promise;
}
async function herdr(args: string[]): Promise<Record<string, unknown>> {
	const output = await execute(["herdr", ...args]);
	return output.trim() ? object(object(JSON.parse(output)).result) : {};
}
async function save(record: RecordState) {
	await mkdir(stateRoot, { recursive: true, mode: 0o700 });
	const path = join(stateRoot, `${record.name}.json`);
	const temp = `${path}.${randomUUID()}.tmp`;
	await writeFile(temp, JSON.stringify(record, null, 2), { mode: 0o600 });
	await rename(temp, path);
}
async function load(name: string): Promise<RecordState | undefined> {
	if (!AGENT_NAME_RE.test(name))
		throw new Error("Name must match [a-z][a-z0-9_-]{0,31}");
	try {
		const value = object(
			JSON.parse(await readFile(join(stateRoot, `${name}.json`), "utf8")),
		);
		if (
			value.version !== 1 ||
			value.name !== name ||
			!["command", "agent"].includes(String(value.kind))
		)
			throw new Error(`Invalid session record: ${name}`);
		text(value.cwd);
		text(value.paneId);
		text(value.tabId);
		return value as unknown as RecordState; // Required control targets have been validated above.
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
		throw error;
	}
}
async function required(name?: string) {
	if (!name) throw new Error("A session name is required");
	const record = await load(name);
	if (!record) throw new Error(`No retained session: ${name}`);
	return record;
}
// The lock is per name and covers launch only, never a command/agent's execution or log reads.
async function locked<T>(name: string, action: () => Promise<T>): Promise<T> {
	if (!AGENT_NAME_RE.test(name)) throw new Error("Invalid session name");
	await mkdir(stateRoot, { recursive: true, mode: 0o700 });
	const lock = join(stateRoot, `${name}.lock`);
	try {
		await writeFile(lock, String(process.pid), { flag: "wx", mode: 0o600 });
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
		const pid = Number(await readFile(lock, "utf8"));
		if (!Number.isSafeInteger(pid) || pid <= 0)
			throw new Error(`Invalid lock; inspect ${lock}`);
		try {
			process.kill(pid, 0);
		} catch (probe) {
			if ((probe as NodeJS.ErrnoException).code !== "ESRCH") throw probe;
			await unlink(lock);
			return locked(name, action);
		}
		throw new Error(
			`Another launch owns ${name}; other names and reads remain available`,
		);
	}
	try {
		return await action();
	} finally {
		await unlink(lock);
	}
}
async function exitState(record: RecordState): Promise<number | undefined> {
	if (!record.runDir) return undefined;
	try {
		const value = object(
			JSON.parse(await readFile(join(record.runDir, "exit.json"), "utf8")),
		).exitCode;
		if (!Number.isInteger(value) || Number(value) < 0 || Number(value) > 255)
			throw new Error("Invalid command exit artifact");
		return Number(value);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
		throw error;
	}
}
async function agentSnapshot(record: RecordState) {
	const agent = object((await herdr(["agent", "get", record.name])).agent);
	if (agent.pane_id !== record.paneId)
		throw new Error(
			`${record.name} now belongs to another pane; refusing to control it`,
		);
	const session = agent.agent_session;
	if (
		session &&
		typeof session === "object" &&
		typeof object(session).value === "string"
	) {
		record.session = text(object(session).value);
		await save(record);
	}
	return agent;
}
async function pane(
	name: string,
	cwd: string,
	anchor?: string,
	direction?: string,
) {
	const anchorId = anchor ?? process.env.HERDR_PANE_ID;
	if (!anchorId)
		throw new Error(
			"HERDR_PANE_ID or --pane is required; focused panes are never used implicitly",
		);
	const current = object((await herdr(["pane", "get", anchorId])).pane);
	const created = direction
		? object(
				(
					await herdr([
						"pane",
						"split",
						"--pane",
						anchorId,
						"--direction",
						direction,
						"--cwd",
						cwd,
						"--no-focus",
					])
				).pane,
			)
		: object(
				(
					await herdr([
						"tab",
						"create",
						"--workspace",
						text(current.workspace_id),
						"--cwd",
						cwd,
						"--label",
						name,
						"--no-focus",
					])
				).root_pane,
			);
	await herdr(["pane", "rename", text(created.pane_id), name]);
	return {
		paneId: text(created.pane_id),
		tabId: text(created.tab_id),
		ownTab: !direction,
	};
}
async function launchCommand(record: RecordState, argv: string[]) {
	record.runDir = join(stateRoot, record.name, randomUUID());
	record.marker = `__HARNESS_DONE_${randomUUID().replaceAll("-", "")}__`;
	await mkdir(record.runDir, { recursive: true, mode: 0o700 });
	const log = join(record.runDir, "output.log");
	const done = join(record.runDir, "exit.json");
	const script = join(record.runDir, "launch.sh");
	// script(1) supplies a real PTY, so humans can operate debuggers/REPLs while output is logged.
	const pagerEnvironment = record.detached
		? ""
		: "export PAGER=cat GIT_PAGER=cat\n";
	await writeFile(
		script,
		`#!/usr/bin/env bash\numask 077\ncd -- ${shellQuote(record.cwd)} || exit 125\n${pagerEnvironment}script -q -e -f -c ${shellQuote(`exec ${argv.map(shellQuote).join(" ")}`)} ${shellQuote(log)}\nstatus=$?\nprintf '{"exitCode":%d}\\n' "$status" > ${shellQuote(`${done}.tmp`)}\nmv -- ${shellQuote(`${done}.tmp`)} ${shellQuote(done)}\nprintf '\\n${record.marker}:%s\\n' "$status"\n`,
		{ mode: 0o700 },
	);
	await save(record);
	try {
		await herdr(["pane", "run", record.paneId, `bash ${shellQuote(script)}`]);
	} catch (error) {
		record.launchError = String(error);
		await save(record);
		throw error;
	}
}
async function waitCommand(record: RecordState, timeout: number) {
	if (record.launchError) throw new Error(record.launchError);
	const runDir = record.runDir;
	if (!runDir) throw new Error("This session has no command log");
	let code = await exitState(record);
	if (code === undefined) {
		if (!record.marker)
			throw new Error("This session has no command to wait for");
		await herdr([
			"pane",
			"wait-output",
			record.paneId,
			"--match",
			record.marker,
			"--timeout",
			String(timeout),
			"--source",
			"recent-unwrapped",
		]);
		code = await exitState(record);
	}
	if (code === undefined)
		throw new Error(
			"No exit artifact; terminal output alone does not prove completion",
		);
	const log = await logTail(join(runDir, "output.log"));
	let agyResult: Record<string, unknown> | undefined;
	if (record.unattended && code === 0) {
		const raw = await logTail(join(runDir, "output.log"), 8 * 1024 * 1024);
		agyResult = parseAgyResult(raw.output);
		if (typeof agyResult.conversation_id === "string") {
			record.session = agyResult.conversation_id;
			await save(record);
		}
	}
	return {
		ok: code === 0,
		status: "exited",
		...record,
		exitCode: code,
		...log,
		...(agyResult
			? {
					agyResult: {
						status: agyResult.status,
						conversation_id: agyResult.conversation_id,
					},
				}
			: {}),
	};
}

async function finishCommand(record: RecordState, timeout: number) {
	const result = await waitCommand(record, timeout);
	if (record.kind !== "command" || record.detached !== false) return result;
	const currentPane = object(
		(await herdr(["pane", "get", record.paneId])).pane,
	);
	if (
		currentPane.pane_id !== record.paneId ||
		currentPane.tab_id !== record.tabId
	)
		throw new Error(
			`${record.name}'s pane ownership changed; preserving the completed pane`,
		);
	if (record.ownTab) {
		const currentTab = object(
			(await herdr(["tab", "get", record.tabId])).tab,
		);
		if (currentTab.tab_id !== record.tabId || currentTab.pane_count !== 1)
			throw new Error(
				`${record.name}'s tab is shared; preserving the completed pane`,
			);
		await herdr(["tab", "close", record.tabId]);
	} else await herdr(["pane", "close", record.paneId]);
	return { ...result, closed: true };
}

async function pruneCommands(options: {
	workspace?: string;
	"dry-run"?: boolean;
	apply?: boolean;
}) {
	if (options["dry-run"] && options.apply)
		throw new Error("Cannot specify both --dry-run and --apply");
	let currentWs = process.env.HERDR_WORKSPACE_ID;
	let currentTabId = process.env.HERDR_TAB_ID;
	const anchor = process.env.HERDR_PANE_ID;
	if (anchor) {
		try {
			const p = object((await herdr(["pane", "get", anchor])).pane);
			currentWs = p.workspace_id ? text(p.workspace_id) : currentWs;
			currentTabId = p.tab_id ? text(p.tab_id) : currentTabId;
		} catch {
			// ignore probe errors
		}
	}
	const targetWs =
		!options.workspace || options.workspace === "current"
			? currentWs
			: options.workspace;

	if (!targetWs)
		throw new Error("Unable to determine target workspace for prune");

	await mkdir(stateRoot, { recursive: true, mode: 0o700 });
	const files = await readdir(stateRoot);
	const names = files
		.filter((f) => f.endsWith(".json") && f !== "sessions.json")
		.map((f) => f.slice(0, -5))
		.filter((name) => AGENT_NAME_RE.test(name));

	const candidates: Array<{
		name: string;
		tabId: string;
		paneId: string;
		exitCode: number;
	}> = [];
	const seenTabs = new Set<string>();

	for (const name of names) {
		const record = await load(name);
		if (!record || record.kind !== "command") continue;
		const code = await exitState(record);
		if (code === undefined) continue;
		if (currentTabId && record.tabId === currentTabId) continue;
		if (seenTabs.has(record.tabId)) continue;

		let tabObj: Record<string, unknown>;
		try {
			tabObj = object((await herdr(["tab", "get", record.tabId])).tab);
		} catch {
			continue;
		}

		if (tabObj.workspace_id !== targetWs) continue;
		if (tabObj.pane_count !== 1) continue;

		let paneObj: Record<string, unknown>;
		try {
			paneObj = object((await herdr(["pane", "get", record.paneId])).pane);
		} catch {
			continue;
		}

		if (
			paneObj.pane_id !== record.paneId ||
			paneObj.tab_id !== record.tabId
		)
			continue;

		seenTabs.add(record.tabId);
		candidates.push({
			name: record.name,
			tabId: record.tabId,
			paneId: record.paneId,
			exitCode: code,
		});
	}

	const apply = Boolean(options.apply);
	if (apply) {
		for (const cand of candidates) {
			await herdr(["tab", "close", cand.tabId]);
		}
	}

	return {
		ok: true,
		action: "prune",
		workspace: targetWs,
		dryRun: !apply,
		count: candidates.length,
		pruned: candidates,
	};
}

const HELP = `harness-run command [--name NAME] [--cwd PATH] [--pane ANCHOR] [--direction right|down] [--detach] [--timeout MS] -- PROGRAM ARG...
harness-run agent --profile PURPOSE --name NAME [--prompt TEXT] [--unattended] [--resume] [--wait] [--timeout MS] [--cwd PATH]
harness-run list
harness-run prune [--workspace current|ID] [--dry-run] [--apply]
harness-run read NAME [--lines N]
harness-run wait NAME [--timeout MS]
harness-run send NAME TEXT [--wait] [--timeout MS]

Default placement: a no-focus tab in the same cwd; finite command tabs close after their result is captured.
Use command --detach --name NAME for retained servers/REPLs; it returns a running handle, NOT readiness.
Prune finished single-pane command tabs: --dry-run (default) previews candidates; --apply closes them.
read/send/wait remain available during retained execution. --timeout bounds waiting, not the visible process.
AGY unattended requires a prompt and verifies process exit + JSON SUCCESS. Interactive AGY has no reliable --wait.
Only use visible command execution for long runs, human observation/collaboration, or an explicit visibility request.
Short commands (including short builds/tests) stay on native tools. HERDR_ENV=1 is required except for --help.
`;

export async function main(args: string[]) {
	const [action, ...rest] = args;
	if (!action || action === "--help" || action === "-h") {
		process.stdout.write(HELP);
		return;
	}
	if (process.env.HERDR_ENV !== "1")
		throw new Error(
			"Not inside Herdr (HERDR_ENV must be 1); no pane was controlled",
		);
	const { values, positionals } = parseArgs({
		args: rest,
		allowPositionals: true,
		options: {
			name: { type: "string" },
			profile: { type: "string" },
			cwd: { type: "string" },
			pane: { type: "string" },
			direction: { type: "string" },
			timeout: { type: "string" },
			lines: { type: "string" },
			prompt: { type: "string" },
			detach: { type: "boolean" },
			wait: { type: "boolean" },
			unattended: { type: "boolean" },
			resume: { type: "boolean" },
			workspace: { type: "string" },
			"dry-run": { type: "boolean" },
			apply: { type: "boolean" },
		},
	});
	const timeout =
		values.timeout === undefined ? 300000 : Number(values.timeout);
	if (!Number.isSafeInteger(timeout) || timeout <= 0)
		throw new Error("--timeout must be positive integer milliseconds");
	if (values.direction && !["right", "down"].includes(values.direction))
		throw new Error("--direction must be right or down");
	let result: Record<string, unknown>;
	if (action === "command" && values.detach && !values.name)
		throw new Error("Detached commands require an explicit --name");
	if (action === "command" || action === "agent") {
		const name =
			values.name ??
			(action === "command" ? `cmd-${randomUUID().slice(0, 8)}` : "");
		if (!AGENT_NAME_RE.test(name))
			throw new Error("A valid --name is required");
		const cwd = await realpath(values.cwd ?? process.cwd());
		let native: string[] = positionals;
		let runner: "omp" | "agy" | undefined;
		if (action === "agent") {
			if (!values.profile) throw new Error("--profile is required");
			const value: unknown = JSON.parse(
				await execute([
					"bun",
					join(root, "omp/profiles.ts"),
					"argv",
					values.profile,
					"--add-dir",
					cwd,
				]),
			);
			if (
				!Array.isArray(value) ||
				!value.every((item) => typeof item === "string") ||
				!["omp", "agy"].includes(value[0])
			)
				throw new Error("Invalid profile argv");
			native = value as string[];
			runner = native[0] as "omp" | "agy";
			if (values.unattended && (runner !== "agy" || !values.prompt))
				throw new Error("--unattended requires an AGY profile and --prompt");
			if (runner === "agy" && values.wait && !values.unattended)
				throw new Error(
					"Interactive AGY completion is unreliable; use --unattended or inspect the retained pane",
				);
		} else if (!native.length)
			throw new Error("command requires PROGRAM ARG... after --");
		const record = await locked(name, async () => {
			let rec = await load(name);
			if (
				rec &&
				(rec.cwd !== cwd ||
					rec.kind !== action ||
					rec.profile !== values.profile ||
					Boolean(rec.unattended) !== Boolean(values.unattended))
			)
				throw new Error(
					"Name already belongs to another cwd/profile/kind; choose another name",
				);
			let alive = false;
			if (rec) {
				try {
					await herdr(["pane", "get", rec.paneId]);
					alive = true;
				} catch {
					/* Closed pane: create a replacement without controlling another pane. */
				}
			}
			if (rec && action === "agent" && !values.unattended && alive) {
				try {
					await agentSnapshot(rec);
					return rec;
				} catch (error) {
					if (!values.resume)
						throw new Error(
							`Retained agent unavailable: ${error}. Use --resume or a new name.`,
						);
				}
			}
			if (rec?.runDir && alive && (await exitState(rec)) === undefined)
				throw new Error(
					`${name} is still running; use read/send/wait instead of launching a duplicate`,
				);
			if (alive && rec) {
				const info = object(
					(await herdr(["pane", "process-info", "--pane", rec.paneId]))
						.process_info,
				);
				if (
					typeof info.shell_pid !== "number" ||
					info.foreground_process_group_id !== info.shell_pid
				)
					throw new Error(
						`${name}'s pane is occupied; refusing to type a command into it`,
					);
			}
			if (values.resume) {
				if (action !== "agent" || !rec?.session)
					throw new Error("No captured agent session identifier to resume");
				native.push(
					runner === "omp" ? "--resume" : "--conversation",
					rec.session,
				);
			}
			const location =
				rec && alive
					? { paneId: rec.paneId, tabId: rec.tabId }
					: await pane(name, cwd, values.pane, values.direction);
			rec = {
				...rec,
				version: 1,
				name,
				kind: action,
				cwd,
				...location,
				profile: values.profile,
				runner,
				unattended: values.unattended,
				detached: action === "command" ? Boolean(values.detach) : undefined,
				launchError: undefined,
			};
			if (action === "command") await launchCommand(rec, native);
			else if (values.unattended)
				await launchCommand(rec, [
					...native,
					"--output-format",
					"json",
					"--print-timeout",
					`${Math.ceil(timeout / 1000)}s`,
					"-p",
					text(values.prompt),
				]);
			else {
				await save(rec);
				await herdr([
					"agent",
					"start",
					name,
					"--kind",
					text(runner),
					"--pane",
					rec.paneId,
					"--timeout",
					String(Math.min(timeout, 60000)),
					"--",
					...native.slice(1),
				]);
				await agentSnapshot(rec);
			}
			return rec;
		});
		if (action === "command" || values.unattended)
			result = values.detach
				? { ok: true, status: "running", ...record, exitCode: null }
				: await finishCommand(
						record,
						timeout + (values.unattended ? 15000 : 0),
					);
		else {
			if (values.prompt)
				await herdr([
					"agent",
					"prompt",
					name,
					values.prompt,
					...(values.wait ? ["--wait", "--timeout", String(timeout)] : []),
				]);
			const agent = await agentSnapshot(record);
			result = {
				ok: agent.agent_status !== "blocked",
				...record,
				agent,
				lifecycleReliable: runner === "omp",
			};
		}
	} else if (action === "list") {
		await mkdir(stateRoot, { recursive: true, mode: 0o700 });
		const names = (await readdir(stateRoot)).filter(
			(name) => name.endsWith(".json") && name !== "sessions.json",
		);
		result = {
			ok: true,
			sessions: await Promise.all(
				names.map(async (name) => {
					const record = await required(name.slice(0, -5));
					try {
						await herdr(["pane", "get", record.paneId]);
						return {
							...record,
							alive: true,
							exitCode: (await exitState(record)) ?? null,
						};
					} catch {
						return { ...record, alive: false };
					}
				}),
			),
		};
	} else if (action === "prune") {
		result = await pruneCommands({
			workspace: values.workspace,
			"dry-run": values["dry-run"],
			apply: values.apply,
		});
	} else {
		const record = await required(positionals[0]);
		if (action === "read") {
			const lines = values.lines === undefined ? 100 : Number(values.lines);
			if (!Number.isSafeInteger(lines) || lines <= 0)
				throw new Error("--lines must be a positive integer");
			let output: string;
			if (record.runDir)
				output = (await logTail(join(record.runDir, "output.log"))).output;
			else {
				await agentSnapshot(record);
				output = await execute([
					"herdr",
					"agent",
					"read",
					record.name,
					"--source",
					"recent-unwrapped",
				]);
			}
			result = {
				ok: true,
				...record,
				output: output.split("\n").slice(-lines).join("\n"),
			};
		} else if (action === "wait") {
			if (record.kind === "command" || record.unattended)
				result = await finishCommand(record, timeout);
			else {
				if (record.runner !== "omp")
					throw new Error("Interactive AGY wait is unreliable");
				await agentSnapshot(record);
				await herdr([
					"agent",
					"wait",
					record.name,
					"--timeout",
					String(timeout),
				]);
				const agent = await agentSnapshot(record);
				result = { ok: agent.agent_status !== "blocked", ...record, agent };
			}
		} else if (action === "send") {
			const input = positionals[1];
			if (input === undefined) throw new Error("send requires NAME TEXT");
			if (record.kind === "command") {
				if ((await exitState(record)) !== undefined)
					throw new Error(
						"Command has exited; launch a new command or reuse this name",
					);
				await herdr(["pane", "run", record.paneId, input]);
				result = { ok: true, ...record };
			} else {
				if (record.unattended)
					throw new Error(
						"Unattended AGY is one-shot; start another turn explicitly",
					);
				if (values.wait && record.runner !== "omp")
					throw new Error("Interactive AGY wait is unreliable");
				await agentSnapshot(record);
				await herdr([
					"agent",
					"prompt",
					record.name,
					input,
					...(values.wait ? ["--wait", "--timeout", String(timeout)] : []),
				]);
				const agent = await agentSnapshot(record);
				result = { ok: agent.agent_status !== "blocked", ...record, agent };
			}
		} else throw new Error(`Unknown action: ${action}`);
	}
	console.log(JSON.stringify(result));
	if (typeof result.exitCode === "number") process.exitCode = result.exitCode;
	else if (result.ok === false) process.exitCode = 1;
}
if (import.meta.main)
	main(process.argv.slice(2)).catch((error) => {
		console.error(
			JSON.stringify({ ok: false, error: String(error.message ?? error) }),
		);
		process.exitCode = 2;
	});
