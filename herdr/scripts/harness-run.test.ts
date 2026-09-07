import { expect, test } from "bun:test";
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
