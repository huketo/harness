import { parseName } from "./name.ts";

export type { Name, ParsedName } from "./name.ts";
export { parseName };

export function greet(input: string): string {
	const parsed = parseName(input);
	switch (parsed.kind) {
		case "ok":
			return `Hello, ${parsed.name}.`;
		case "empty":
			return "Tell me your name.";
		case "too-long":
			return `Use at most ${parsed.limit} characters.`;
	}
}
