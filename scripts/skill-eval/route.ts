#!/usr/bin/env node
/**
 * Description-based routing check: asks the agent, once per prompt of a
 * routing file, which skill it would pick from the candidate skills'
 * descriptions alone. It does not observe actual skill activation.
 */

import { killActiveGroups } from "./lib/run/agent.ts";
import { main } from "./lib/route/runner.ts";

if (import.meta.main) {
	for (const signal of ["SIGINT", "SIGTERM"] as const)
		process.on(signal, () => {
			killActiveGroups();
			process.exit(130);
		});
	process.exit(await main(process.argv.slice(2)));
}
