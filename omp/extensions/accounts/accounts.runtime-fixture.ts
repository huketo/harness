import type { UsageProvider } from "@oh-my-pi/pi-ai";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

const provider = "openai-codex";
const baseUrl = process.env.HARNESS_ACCOUNTS_RUNTIME_BASE_URL;
if (!baseUrl) {
	throw new Error(
		"HARNESS_ACCOUNTS_RUNTIME_BASE_URL is required by the account runtime fixture.",
	);
}

const usage: UsageProvider = {
	id: provider,
	supports: ({ provider: candidate }) => candidate === provider,
	async fetchUsage({ credential }) {
		const usedFraction = credential.accessToken?.endsWith("-1") ? 0.1 : 0.9;
		return {
			provider,
			fetchedAt: Date.now(),
			metadata: { planType: "plus" },
			limits: [
				{
					id: "openai-codex:primary",
					label: "5 hours",
					scope: { provider, windowId: "5h", shared: true },
					window: {
						id: "5h",
						label: "5 hours",
						durationMs: 5 * 60 * 60 * 1000,
						resetsAt: Date.now() + 5 * 60 * 60 * 1000,
					},
					amount: { unit: "percent", usedFraction },
					status: "ok",
				},
			],
		};
	},
};

export default function runtimeProviderFixture(pi: ExtensionAPI): void {
	pi.registerProvider(provider, {
		baseUrl,
		api: "openai-codex-responses",
		usage,
		oauth: {
			name: "Synthetic OpenAI Codex",
			async login() {
				throw new Error("Synthetic runtime provider does not support login.");
			},
			async refreshToken(credentials) {
				return credentials;
			},
			getApiKey(credentials) {
				return credentials.access;
			},
		},
		models: [
			{
				id: "runtime-routing-model",
				name: "Synthetic Runtime Routing Model",
				api: "openai-codex-responses",
				reasoning: false,
				input: ["text"],
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
				contextWindow: 16_384,
				maxTokens: 1_024,
				preferWebsockets: false,
			},
		],
	});
}
