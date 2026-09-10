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

function fakeHerdr() {
	const dir = mkdtempSync(join(tmpdir(), "harness-run-"));
	const calls = join(dir, "calls");
	const executable = join(dir, "herdr");
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
	pane:rename)
		printf '{"result":{}}\\n'
		;;
	pane:run)
		bash -c "$4" >/dev/null 2>&1
		printf '{"result":{}}\\n'
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
	*)
		printf 'unexpected fake herdr call: %s %s\\n' "$1" "$2" >&2
		exit 1
		;;
esac
`,
		{ mode: 0o755 },
	);
	return {
		dir,
		calls,
		env: {
			...process.env,
			FAKE_HERDR_CALLS: calls,
			FAKE_HERDR_DIR: dir,
			HERDR_ENV: "1",
			HERDR_PANE_ID: "w:anchor",
			HERDR_WORKSPACE_ID: "w",
			PATH: `${dir}:${process.env.PATH ?? ""}`,
			XDG_STATE_HOME: join(dir, "state"),
		},
	};
}

function runHarness(args: string[], env: NodeJS.ProcessEnv) {
	return Bun.spawnSync([process.execPath, import.meta.path.replace(/\.test\.ts$/, ".ts"), ...args], {
		env,
		stdout: "pipe",
		stderr: "pipe",
	});
}

test("completed commands preserve their result and close their owned tab", () => {
	const fake = fakeHerdr();
	try {
		const child = runHarness(
			["command", "--name", "finite", "--cwd", fake.dir, "--", "printf", "visible"],
			fake.env,
		);
		expect(child.exitCode).toBe(0);
		const result = JSON.parse(child.stdout.toString());
		expect(result.exitCode).toBe(0);
		expect(result.output).toContain("visible");
		expect(readFileSync(fake.calls, "utf8")).toContain("tab\u001fclose\u001fw:t1\u001f");
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
				writeFileSync(join(runDir, "exit.json"), JSON.stringify({ exitCode: 0 }));
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
		setup("running-cmd", "command", "w:t_running", "w:p_running", "w", 1, false);
		// 4. current tab (anchor tab, must be preserved)
		setup("current-cmd", "command", "w:t1", "w:p_curr", "w", 1, true);
		// 5. shared tab (>1 panes, must be preserved)
		setup("shared-cmd", "command", "w:t_shared", "w:p_shared", "w", 2, true);
		// 6. foreign workspace tab (workspace 'other', must be preserved)
		setup("foreign-cmd", "command", "other:t_foreign", "other:p_foreign", "other", 1, true);

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
