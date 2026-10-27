import { expect, test } from "bun:test";
import {
	mkdirSync,
	mkdtempSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseAgyResult, shellQuote } from "./harness-run";

test("terminal command arguments stay literal across the shell boundary", () => {
	const args = [
		"",
		"space value",
		"a'b",
		'"quoted"',
		"$(printf INJECTED)",
		"x; printf INJECTED",
		"line\nbreak",
	];
	const process = Bun.spawnSync([
		"bash",
		"-c",
		`printf '%s\\0' ${args.map(shellQuote).join(" ")}`,
	]);
	expect(process.exitCode).toBe(0);
	expect(process.stdout.toString()).toBe(`${args.join("\0")}\0`);
});

test("AGY transport success does not hide a failed or empty model turn", () => {
	expect(() =>
		parseAgyResult('{"status":"FAILURE","response":"quota exhausted"}'),
	).toThrow();
	expect(() => parseAgyResult('{"status":"SUCCESS","response":" "}')).toThrow();
	const result = parseAgyResult(
		'PTY header\r\n{"status":"SUCCESS","response":"actual answer","conversation_id":"retained"}\r\nPTY footer',
	);
	expect(result.response).toBe("actual answer");
	expect(result.conversation_id).toBe("retained");
});

interface FakeHerdr {
	dir: string;
	calls: string;
	env: NodeJS.ProcessEnv;
}

function fakeHerdr(): FakeHerdr {
	const dir = mkdtempSync(join(tmpdir(), "harness-run-"));
	const calls = join(dir, "calls");
	writeFileSync(calls, "");
	const executable = join(dir, "herdr");
	const bunExecutable = join(dir, "bun");
	writeFileSync(
		executable,
		`#!/usr/bin/env bash
set -euo pipefail
printf '%s\\037' "$@" >> "$FAKE_HERDR_CALLS"
printf '\\n' >> "$FAKE_HERDR_CALLS"
case "$1:$2" in
	pane:get)
		if [[ -f "$FAKE_HERDR_DIR/panes/$3.json" ]]; then
			cat "$FAKE_HERDR_DIR/panes/$3.json"
		else
			printf '{"result":{"pane":{"pane_id":"%s","tab_id":"w:t1","workspace_id":"w"}}}\\n' "$3"
		fi
		;;
	tab:create)
		printf '{"result":{"root_pane":{"pane_id":"w:p1","tab_id":"w:t1"}}}\\n'
		;;
	agent:get)
		if [[ -f "$FAKE_HERDR_DIR/agents/$3.json" ]]; then
			cat "$FAKE_HERDR_DIR/agents/$3.json"
		else
			printf '{"result":{"agent":{"agent":"agy","agent_status":"idle","pane_id":"w:p1","screen_detection_skipped":true}}}\n'
		fi
		;;
	agent:start)
		printf '{"result":{}}\n'
		;;
	agent:prompt|agent:wait)
		printf '{"result":{}}\n'
		;;
	agent:read)
		if [[ -f "$FAKE_HERDR_DIR/outputs/$3.txt" ]]; then
			cat "$FAKE_HERDR_DIR/outputs/$3.txt"
		else
			printf 'no captured output\n'
		fi
		;;
	pane:rename)
		printf '{"result":{}}\\n'
		;;
	pane:run)
		bash -c "$4" >/dev/null 2>&1
		printf '{"result":{}}\\n'
		;;
	pane:process-info)
		printf '{"result":{"process_info":{"shell_pid":10,"foreground_process_group_id":10}}}\\n'
		;;
	pane:wait-output)
		printf '{"result":{}}\\n'
		;;
	tab:get)
		if [[ -f "$FAKE_HERDR_DIR/tabs/$3.json" ]]; then
			cat "$FAKE_HERDR_DIR/tabs/$3.json"
		else
			printf '{"result":{"tab":{"tab_id":"%s","workspace_id":"w","pane_count":1}}}\\n' "$3"
		fi
		;;
	tab:close)
		printf '{"result":{}}\\n'
		;;
	pane:close)
		printf '{"result":{}}\\n'
		;;
	*)
		printf 'unexpected fake herdr call: %s %s\\n' "$1" "$2" >&2
		exit 1
		;;
esac
`,
		{ mode: 0o755 },
	);
	writeFileSync(
		bunExecutable,
		`#!/usr/bin/env bash
printf '["agy","--model","fake-model"]\\n'
`,
		{ mode: 0o755 },
	);
	return {
		dir,
		calls,
		env: {
			...process.env,
			HARNESS_DELEGATION: undefined,
			FAKE_HERDR_CALLS: calls,
			FAKE_HERDR_DIR: dir,
			HERDR_ENV: "1",
			HERDR_PANE_ID: "w:anchor",
			HERDR_WORKSPACE_ID: "w",
			HERDR_SOCKET_PATH: join(dir, "herdr.sock"),
			PATH: `${dir}:${process.env.PATH ?? ""}`,
			XDG_STATE_HOME: join(dir, "state"),
		},
	};
}

function runHarness(args: string[], env: NodeJS.ProcessEnv) {
	return Bun.spawnSync(
		[process.execPath, import.meta.path.replace(/\.test\.ts$/, ".ts"), ...args],
		{
			env,
			stdout: "pipe",
			stderr: "pipe",
		},
	);
}

function retainAgent(
	fake: FakeHerdr,
	options: {
		name: string;
		status?: "idle" | "done" | "working" | "blocked" | "unknown";
		paneId?: string;
		tabId?: string;
		ownTab?: boolean;
		paneCount?: number;
		socketPath?: string | null;
		ownerPaneId?: string | null;
	},
) {
	const paneId = options.paneId ?? `w:p_${options.name}`;
	const tabId = options.tabId ?? `w:t_${options.name}`;
	const stateDir = join(fake.dir, "state", "harness-run");
	for (const subdir of ["agents", "outputs", "panes", "tabs"])
		mkdirSync(join(fake.dir, subdir), { recursive: true });
	mkdirSync(stateDir, { recursive: true });
	const record: Record<string, unknown> = {
		version: 1,
		name: options.name,
		kind: "agent",
		cwd: fake.dir,
		paneId,
		tabId,
		profile: "fake",
		runner: "agy",
		unattended: false,
		ownTab: options.ownTab ?? true,
	};
	if (options.socketPath !== null)
		record.socketPath =
			options.socketPath ?? String(fake.env.HERDR_SOCKET_PATH);
	if (options.ownerPaneId !== null)
		record.ownerPaneId = options.ownerPaneId ?? String(fake.env.HERDR_PANE_ID);
	writeFileSync(join(stateDir, `${options.name}.json`), JSON.stringify(record));
	writeFileSync(
		join(fake.dir, "agents", `${options.name}.json`),
		JSON.stringify({
			result: {
				agent: {
					agent: "agy",
					agent_status: options.status ?? "idle",
					pane_id: paneId,
					screen_detection_skipped: true,
				},
			},
		}),
	);
	writeFileSync(
		join(fake.dir, "panes", `${paneId}.json`),
		JSON.stringify({
			result: { pane: { pane_id: paneId, tab_id: tabId, workspace_id: "w" } },
		}),
	);
	writeFileSync(
		join(fake.dir, "tabs", `${tabId}.json`),
		JSON.stringify({
			result: {
				tab: {
					tab_id: tabId,
					workspace_id: "w",
					pane_count: options.paneCount ?? 1,
				},
			},
		}),
	);
	writeFileSync(
		join(fake.dir, "outputs", `${options.name}.txt`),
		`${options.name} captured response\n`,
	);
	return join(stateDir, `${options.name}.json`);
}

test("completed commands preserve their result and close their owned tab", () => {
	const fake = fakeHerdr();
	try {
		const child = runHarness(
			[
				"command",
				"--name",
				"finite",
				"--cwd",
				fake.dir,
				"--",
				"printf",
				"visible",
			],
			fake.env,
		);
		expect(child.exitCode).toBe(0);
		const result = JSON.parse(child.stdout.toString());
		expect(result.exitCode).toBe(0);
		expect(result.output).toContain("visible");
		expect(readFileSync(fake.calls, "utf8")).toContain(
			"tab\u001fclose\u001fw:t1\u001f",
		);
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);

test("detached commands require a stable name", () => {
	const fake = fakeHerdr();
	try {
		const child = runHarness(
			["command", "--detach", "--cwd", fake.dir, "--", "sleep", "1"],
			fake.env,
		);
		expect(child.exitCode).toBe(2);
		expect(child.stderr.toString()).toContain(
			"Detached commands require an explicit --name",
		);
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
});

test("finite commands disable terminal pagers", () => {
	const fake = fakeHerdr();
	try {
		const child = runHarness(
			[
				"command",
				"--name",
				"pager",
				"--cwd",
				fake.dir,
				"--",
				"bash",
				"-c",
				'printf "%s/%s" "$PAGER" "$GIT_PAGER"',
			],
			{ ...fake.env, GIT_PAGER: "less", PAGER: "less" },
		);
		expect(child.exitCode).toBe(0);
		expect(JSON.parse(child.stdout.toString()).output).toContain("cat/cat");
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);

test("prune dry-run reports single-pane completed command tabs and preserves protected tabs", () => {
	const fake = fakeHerdr();
	try {
		const stateDir = join(fake.dir, "state", "harness-run");
		mkdirSync(join(fake.dir, "panes"), { recursive: true });
		mkdirSync(join(fake.dir, "tabs"), { recursive: true });
		mkdirSync(stateDir, { recursive: true });

		const setup = (
			name: string,
			kind: string,
			tabId: string,
			paneId: string,
			ws: string,
			paneCount: number,
			hasExit: boolean,
		) => {
			const runDir = join(stateDir, name, "run1");
			mkdirSync(runDir, { recursive: true });
			if (hasExit) {
				writeFileSync(
					join(runDir, "exit.json"),
					JSON.stringify({ exitCode: 0 }),
				);
			}
			writeFileSync(
				join(stateDir, `${name}.json`),
				JSON.stringify({
					version: 1,
					name,
					kind,
					cwd: fake.dir,
					paneId,
					tabId,
					runDir: kind === "command" ? runDir : undefined,
				}),
			);
			writeFileSync(
				join(fake.dir, "tabs", `${tabId}.json`),
				JSON.stringify({
					result: {
						tab: {
							tab_id: tabId,
							workspace_id: ws,
							pane_count: paneCount,
						},
					},
				}),
			);
			writeFileSync(
				join(fake.dir, "panes", `${paneId}.json`),
				JSON.stringify({
					result: {
						pane: {
							pane_id: paneId,
							tab_id: tabId,
							workspace_id: ws,
						},
					},
				}),
			);
		};

		// 1. target completed command tab
		setup("finite-target", "command", "w:t_target", "w:p_target", "w", 1, true);
		// 2. agent tab (must be preserved)
		setup("agent-session", "agent", "w:t_agent", "w:p_agent", "w", 1, false);
		// 3. running command tab (no exit artifact, must be preserved)
		setup(
			"running-cmd",
			"command",
			"w:t_running",
			"w:p_running",
			"w",
			1,
			false,
		);
		// 4. current tab (anchor tab, must be preserved)
		setup("current-cmd", "command", "w:t1", "w:p_curr", "w", 1, true);
		// 5. shared tab (>1 panes, must be preserved)
		setup("shared-cmd", "command", "w:t_shared", "w:p_shared", "w", 2, true);
		// 6. foreign workspace tab (workspace 'other', must be preserved)
		setup(
			"foreign-cmd",
			"command",
			"other:t_foreign",
			"other:p_foreign",
			"other",
			1,
			true,
		);

		// Test dry-run
		const dryChild = runHarness(
			["prune", "--workspace", "current", "--dry-run"],
			fake.env,
		);
		expect(dryChild.exitCode).toBe(0);
		const dryResult = JSON.parse(dryChild.stdout.toString());
		expect(dryResult.ok).toBe(true);
		expect(dryResult.dryRun).toBe(true);
		expect(dryResult.count).toBe(1);
		expect(dryResult.pruned[0].name).toBe("finite-target");
		expect(dryResult.pruned[0].tabId).toBe("w:t_target");
		// Ensure tab close was NOT called during dry-run
		expect(readFileSync(fake.calls, "utf8")).not.toContain("tab\u001fclose");

		// Test apply
		const applyChild = runHarness(
			["prune", "--workspace", "current", "--apply"],
			fake.env,
		);
		expect(applyChild.exitCode).toBe(0);
		const applyResult = JSON.parse(applyChild.stdout.toString());
		expect(applyResult.ok).toBe(true);
		expect(applyResult.dryRun).toBe(false);
		expect(applyResult.count).toBe(1);
		expect(applyResult.pruned[0].name).toBe("finite-target");
		// Ensure tab close was called ONLY for target
		const calls = readFileSync(fake.calls, "utf8");
		expect(calls).toContain("tab\u001fclose\u001fw:t_target\u001f");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t_agent");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t_running");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t1");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t_shared");
		expect(calls).not.toContain("tab\u001fclose\u001fother:t_foreign");
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 20000);

test("opt-in interactive AGY reports observed lifecycle separately from validated completion", () => {
	const fake = fakeHerdr();
	try {
		mkdirSync(join(fake.dir, "outputs"), { recursive: true });
		writeFileSync(
			join(fake.dir, "outputs", "worker.txt"),
			"completed worker response\n",
		);
		const env = { ...fake.env, HARNESS_DELEGATION: "agy" };
		const started = runHarness(
			[
				"agent",
				"--profile",
				"fake",
				"--name",
				"worker",
				"--cwd",
				fake.dir,
				"--prompt=perform the assigned slice",
				"--wait",
			],
			env,
		);
		expect(started.exitCode).toBe(0);
		const startResult = JSON.parse(started.stdout.toString());
		expect(startResult.agentStatus).toBe("idle");
		expect(startResult.lifecycleSource).toBe("integration");
		expect(startResult.output).toContain("completed worker response");
		expect(startResult.settled).toBe(true);
		expect(startResult.activityObserved).toBe(true);
		expect(startResult.completionValidated).toBe(false);
		const saved = JSON.parse(
			readFileSync(
				join(fake.dir, "state", "harness-run", "worker.json"),
				"utf8",
			),
		);
		expect(saved.socketPath).toBe(env.HERDR_SOCKET_PATH);
		expect(saved.ownerPaneId).toBe(env.HERDR_PANE_ID);

		const sent = runHarness(["send", "worker", "--", "next slice"], env);
		expect(sent.exitCode).toBe(0);
		const sendResult = JSON.parse(sent.stdout.toString());
		expect(sendResult.activityObserved).toBe(true);
		expect(sendResult.completionValidated).toBe(false);

		const waited = runHarness(["wait", "worker", "--timeout", "1000"], env);
		expect(waited.exitCode).toBe(0);
		const waitResult = JSON.parse(waited.stdout.toString());
		expect(waitResult.agentStatus).toBe("idle");
		expect(waitResult.output).toContain("completed worker response");
		expect(waitResult.settled).toBe(true);
		expect(waitResult.completionValidated).toBe(false);

		const calls = readFileSync(fake.calls, "utf8");
		expect(calls).toContain(
			"agent\u001fprompt\u001fworker\u001fperform the assigned slice\u001f--wait\u001f--timeout\u001f",
		);
		expect(calls).toContain(
			"agent\u001fprompt\u001fworker\u001fnext slice\u001f--wait\u001f--until\u001fworking\u001f--until\u001fblocked\u001f--timeout\u001f5000\u001f",
		);
		expect(calls).toContain(
			"agent\u001fread\u001fworker\u001f--source\u001frecent-unwrapped\u001f",
		);
		expect(calls).not.toContain("workspace\u001fcreate");
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);

test("opt-in reuse and send reject non-ready agents without submitting a prompt", () => {
	const fake = fakeHerdr();
	try {
		const env = { ...fake.env, HARNESS_DELEGATION: "agy" };
		retainAgent(fake, { name: "reused", status: "working" });
		const reused = runHarness(
			[
				"agent",
				"--profile",
				"fake",
				"--name",
				"reused",
				"--cwd",
				fake.dir,
				"--prompt=new work",
			],
			env,
		);
		expect(reused.exitCode).toBe(2);
		expect(reused.stderr.toString()).toContain("reused is working");

		for (const status of ["working", "blocked", "unknown"] as const) {
			retainAgent(fake, { name: `send-${status}`, status });
			const sent = runHarness(
				["send", `send-${status}`, "--", "must not be delivered"],
				env,
			);
			expect(sent.exitCode).toBe(2);
			expect(sent.stderr.toString()).toContain(`is ${status}`);
			expect(sent.stderr.toString()).toContain("No input was resent");
		}
		expect(readFileSync(fake.calls, "utf8")).not.toContain(
			"agent\u001fprompt\u001f",
		);
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);

test("opt-in control rejects foreign sessions, legacy records, and foreign coordinators", () => {
	const fake = fakeHerdr();
	try {
		const env = { ...fake.env, HARNESS_DELEGATION: "agy" };
		retainAgent(fake, {
			name: "foreign-session",
			socketPath: join(fake.dir, "another.sock"),
		});
		const foreignSession = runHarness(
			["send", "foreign-session", "--", "do not send"],
			env,
		);
		expect(foreignSession.exitCode).toBe(2);
		expect(foreignSession.stderr.toString()).toContain(
			"belongs to another Herdr session",
		);

		retainAgent(fake, {
			name: "legacy",
			socketPath: null,
			ownerPaneId: null,
		});
		const legacy = runHarness(["wait", "legacy"], env);
		expect(legacy.exitCode).toBe(2);
		expect(legacy.stderr.toString()).toContain(
			"predates Herdr session ownership",
		);

		retainAgent(fake, {
			name: "foreign-owner",
			ownerPaneId: "w:another-coordinator",
		});
		const foreignStart = runHarness(
			[
				"agent",
				"--profile",
				"fake",
				"--name",
				"foreign-owner",
				"--cwd",
				fake.dir,
				"--prompt=do not send",
			],
			env,
		);
		expect(foreignStart.exitCode).toBe(2);
		expect(foreignStart.stderr.toString()).toContain(
			"belongs to another harness-run coordinator",
		);
		const foreignClose = runHarness(["close", "foreign-owner"], env);
		expect(foreignClose.exitCode).toBe(2);
		expect(foreignClose.stderr.toString()).toContain(
			"belongs to another harness-run coordinator",
		);

		const calls = readFileSync(fake.calls, "utf8");
		expect(calls).not.toContain("agent\u001fprompt\u001f");
		expect(calls).not.toContain("tab\u001fclose\u001f");
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);

test("opt-in close only closes an owned idle single-pane agent tab and preserves its record", () => {
	const fake = fakeHerdr();
	try {
		const env = { ...fake.env, HARNESS_DELEGATION: "agy" };
		const ownedRecord = retainAgent(fake, { name: "owned", status: "idle" });
		const owned = runHarness(["close", "owned"], env);
		expect(owned.exitCode).toBe(0);
		expect(JSON.parse(owned.stdout.toString()).closed).toBe(true);
		expect(readFileSync(ownedRecord, "utf8")).toContain('"name":"owned"');

		retainAgent(fake, {
			name: "shared",
			status: "done",
			paneCount: 2,
		});
		const shared = runHarness(["close", "shared"], env);
		expect(shared.exitCode).toBe(2);
		expect(shared.stderr.toString()).toContain("tab is shared");

		retainAgent(fake, {
			name: "user-pane",
			status: "idle",
			ownTab: false,
		});
		const userPane = runHarness(["close", "user-pane"], env);
		expect(userPane.exitCode).toBe(2);
		expect(userPane.stderr.toString()).toContain("does not own its tab");

		retainAgent(fake, {
			name: "caller",
			status: "idle",
			paneId: String(env.HERDR_PANE_ID),
		});
		const caller = runHarness(["close", "caller"], env);
		expect(caller.exitCode).toBe(2);
		expect(caller.stderr.toString()).toContain("current caller pane");

		const calls = readFileSync(fake.calls, "utf8");
		expect(calls).toContain("tab\u001fclose\u001fw:t_owned\u001f");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t_shared\u001f");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t_user-pane\u001f");
		expect(calls).not.toContain("tab\u001fclose\u001fw:t_caller\u001f");
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);

test("legacy mode keeps interactive AGY wait and close disabled", () => {
	const fake = fakeHerdr();
	try {
		retainAgent(fake, {
			name: "legacy-default",
			socketPath: null,
			ownerPaneId: null,
		});
		const send = runHarness(
			["send", "legacy-default", "--wait", "--", "not sent"],
			fake.env,
		);
		expect(send.exitCode).toBe(2);
		expect(send.stderr.toString()).toContain(
			"unreliable unless HARNESS_DELEGATION=agy",
		);
		const close = runHarness(["close", "legacy-default"], fake.env);
		expect(close.exitCode).toBe(2);
		expect(close.stderr.toString()).toContain(
			"close requires HARNESS_DELEGATION=agy",
		);
		expect(readFileSync(fake.calls, "utf8")).not.toContain(
			"agent\u001fprompt\u001f",
		);
	} finally {
		rmSync(fake.dir, { recursive: true, force: true });
	}
}, 15000);
