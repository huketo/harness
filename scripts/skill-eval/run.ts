#!/usr/bin/env node
/**
 * skill-eval runner: executes each suite case per arm in an isolated headless
 * `claude -p` session and writes the run outputs defined in lib/schema.ts.
 */

import { killActiveGroups } from "./lib/run/agent.ts";
import { main } from "./lib/run/runner.ts";

if (import.meta.main) {
	for (const signal of ["SIGINT", "SIGTERM"] as const)
		process.on(signal, () => {
			killActiveGroups();
			process.exit(130);
		});
	process.exit(await main(process.argv.slice(2)));
}
