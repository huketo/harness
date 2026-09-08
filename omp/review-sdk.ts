import { realpathSync } from "node:fs";
import { dirname } from "node:path";
import type * as Sdk from "@oh-my-pi/pi-coding-agent";
import type * as Runtime from "@oh-my-pi/pi-coding-agent/modes/runtime-init";
import type * as Thinking from "@oh-my-pi/pi-coding-agent/thinking";
import type * as Utils from "@oh-my-pi/pi-utils";

// Use the installation selected by PATH, not Bun's implicit package-download cache.
const executable = Bun.which("omp");
if (!executable)
	throw new Error(
		"The restricted reviewer requires an installed omp executable",
	);
const directory = dirname(realpathSync(executable));
export function resolveReviewDependency(specifier: string): string {
	return Bun.resolveSync(specifier, directory);
}

// Runtime-selected installation paths cannot use static bare imports in a standalone checkout.
export const sdk = (await import(
	resolveReviewDependency("@oh-my-pi/pi-coding-agent")
)) as typeof Sdk;
export const runtime = (await import(
	resolveReviewDependency("@oh-my-pi/pi-coding-agent/modes/runtime-init")
)) as typeof Runtime;
export const thinking = (await import(
	resolveReviewDependency("@oh-my-pi/pi-coding-agent/thinking")
)) as typeof Thinking;
export const utils = (await import(
	resolveReviewDependency("@oh-my-pi/pi-utils")
)) as typeof Utils;
