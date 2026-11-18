declare const nameBrand: unique symbol;
export type Name = string & { readonly [nameBrand]: true };

export type ParsedName = { kind: "ok"; name: Name } | { kind: "empty" } | { kind: "too-long"; limit: number };

const LIMIT = 40;

export function parseName(input: string): ParsedName {
	const trimmed = input.trim();
	if (trimmed === "") return { kind: "empty" };
	if (trimmed.length > LIMIT) return { kind: "too-long", limit: LIMIT };
	return { kind: "ok", name: trimmed as Name };
}
