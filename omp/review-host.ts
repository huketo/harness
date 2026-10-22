/**
 * Trusted extension module loaded by omp/review.ts into the PATH `omp`
 * executable (`omp --mode rpc ... --trusted-extension review-host.ts`). The
 * `@oh-my-pi/*` imports resolve to that process's own runtime, so the reviewer
 * shares the SDK and model catalog reported by `omp models`. Not an
 * installable extension.
 *
 * omp loads extension factories before it creates its own session, and that
 * session is what evaluates ambient custom tools and starts MCP servers. The
 * factory therefore runs the whole review and terminates the process instead
 * of returning, so the host session is never created.
 */
import { THINKING_EFFORTS } from "@oh-my-pi/pi-ai";
import * as sdk from "@oh-my-pi/pi-coding-agent";
import { initializeExtensions } from "@oh-my-pi/pi-coding-agent/modes/runtime-init";
import { postmortem, sanitizeText } from "@oh-my-pi/pi-utils";
import { REVIEW_IPC_ENV, runHostedReview } from "./review";

export default async function reviewHost(): Promise<never> {
	const ipcDir = process.env[REVIEW_IPC_ENV];
	// A trusted-extension load failure aborts omp before its session exists.
	if (!ipcDir)
		throw new Error(
			`review-host requires ${REVIEW_IPC_ENV}; launch it through omp/review.ts`,
		);
	// omp guards process.exit while extensions load; postmortem.exitProcess is
	// its host-owned exit through that guard.
	const launcher = process.ppid;
	setInterval(() => {
		if (process.ppid !== launcher) postmortem.exitProcess(1);
	}, 1000).unref();
	let code = 1;
	try {
		code = await runHostedReview(ipcDir, {
			sdk,
			initializeExtensions,
			thinkingEfforts: THINKING_EFFORTS,
			sanitizeText,
		});
	} finally {
		await postmortem.cleanup();
		postmortem.exitProcess(code);
	}
}
