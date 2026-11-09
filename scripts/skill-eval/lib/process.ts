import type { ChildProcess } from "node:child_process";
import { constants } from "node:os";
import type { Readable } from "node:stream";

/** Reads a child's piped output as UTF-8; resolves with what was read if the stream errors. */
export function collectText(stream: Readable): Promise<string> {
	return new Promise((resolve) => {
		let text = "";
		stream.setEncoding("utf8");
		stream.on("data", (chunk: string) => {
			text += chunk;
		});
		stream.once("end", () => resolve(text));
		stream.once("error", () => resolve(text));
	});
}

/**
 * Resolves with the child's exit code when it exits, or with 128 plus the
 * signal number when a signal ended it (the shell convention, e.g. 143 for
 * SIGTERM); rejects when the child could not be started.
 */
export function exitStatus(child: ChildProcess): Promise<number> {
	return new Promise((resolve, reject) => {
		child.once("error", reject);
		child.once("exit", (code, signal) => resolve(code ?? 128 + (signal ? constants.signals[signal] : 0)));
	});
}
