import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type {
	CreateAgentSessionResult,
	ExtensionFactory,
} from "@oh-my-pi/pi-coding-agent";
import {
	assertRestrictedReviewCapabilities,
	buildRestrictedReviewSessionOptions,
	initializeReviewExtensions,
} from "./review";
import { resolveReviewDependency, sdk } from "./review-sdk";

const { createAgentSession, Settings } = sdk;
// Match the OMP installation selected by the launcher rather than Bun's package cache.
const { createMockModel } = await import(
	resolveReviewDependency("@oh-my-pi/pi-ai/providers/mock")
);

test("restricted reviewer excludes ambient capabilities and inline extensions after initialization", async () => {
	const root = await mkdtemp(join(tmpdir(), "harness-review-"));
	const model = createMockModel();
	let inlineFactoryRan = false;
	const inlineExtension: ExtensionFactory = () => {
		inlineFactoryRan = true;
	};
	let result: CreateAgentSessionResult | undefined;
	try {
		result = await createAgentSession({
			...buildRestrictedReviewSessionOptions({
				cwd: root,
				agentDir: root,
				settings: Settings.isolated(),
			}),
			model,
			getApiKey: async () => "synthetic-test-key",
			extensions: [inlineExtension],
		});
		await initializeReviewExtensions(result.session);
		const capabilities = assertRestrictedReviewCapabilities(result);
		expect(capabilities).toEqual({
			enabledTools: ["glob", "grep", "read"],
			registeredTools: ["glob", "grep", "read"],
			mountedTools: [],
			evalBridgeTools: ["glob", "grep", "read"],
			extensions: [],
			mcpEnabled: false,
		});
		expect(inlineFactoryRan).toBe(false);
	} finally {
		if (result && !result.session.isDisposed) await result.session.dispose();
		await rm(root, { recursive: true, force: true });
	}
});
