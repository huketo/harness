/**
 * Glob matching for check paths, with the semantics the checks were written
 * against (Bun's `Glob.match`): `*` and `?` stay within one path segment and,
 * unlike `path.matchesGlob`, also match names that start with a dot; `**` as a
 * whole segment spans zero or more segments; `[...]`/`[!...]`/`[^...]`
 * classes, `{a,b}` alternation, `\` escapes, and a leading `!` negation.
 * Inputs are file paths, so no attempt is made to mirror Bun on paths that
 * end with `/`.
 */

const SPECIAL = /[.*+?^${}()|[\]\\/]/g;
const escapeChar = (c: string) => c.replace(SPECIAL, "\\$&");

/** Index of the `}` closing the `{` at `open`, or -1. */
function closingBrace(pattern: string, open: number): number {
	let depth = 0;
	for (let i = open; i < pattern.length; i++) {
		const c = pattern[i];
		if (c === "\\") i++;
		else if (c === "{") depth++;
		else if (c === "}" && --depth === 0) return i;
	}
	return -1;
}

/** Splits brace contents at top-level commas. */
function alternatives(body: string): string[] {
	const parts: string[] = [];
	let depth = 0;
	let start = 0;
	for (let i = 0; i < body.length; i++) {
		const c = body[i];
		if (c === "\\") i++;
		else if (c === "{") depth++;
		else if (c === "}") depth--;
		else if (c === "," && depth === 0) {
			parts.push(body.slice(start, i));
			start = i + 1;
		}
	}
	parts.push(body.slice(start));
	return parts;
}

function compile(pattern: string): string {
	let out = "";
	for (let i = 0; i < pattern.length; i++) {
		const c = pattern[i];
		if (c === "\\") {
			if (i + 1 < pattern.length) out += escapeChar(pattern[++i]);
			else out += "\\\\";
		} else if (c === "*") {
			let end = i;
			while (pattern[end + 1] === "*") end++;
			const globstar = end > i && (i === 0 || pattern[i - 1] === "/");
			if (globstar && pattern[end + 1] === "/") {
				out += "(?:[^/]*/)*";
				i = end + 1;
			} else if (globstar && end + 1 === pattern.length) {
				out += ".*";
				i = end;
			} else {
				out += "[^/]*";
				i = end;
			}
		} else if (c === "?") {
			out += "[^/]";
		} else if (c === "[") {
			let j = i + 1;
			const negate = pattern[j] === "!" || pattern[j] === "^";
			if (negate) j++;
			if (pattern[j] === "]") j++;
			while (j < pattern.length && pattern[j] !== "]") j += pattern[j] === "\\" ? 2 : 1;
			if (j >= pattern.length) {
				out += "\\[";
				continue;
			}
			const body = pattern.slice(i + 1 + (negate ? 1 : 0), j);
			let cls = "";
			for (let k = 0; k < body.length; k++) {
				const b = body[k];
				if (b === "\\" && k + 1 < body.length) cls += `\\${body[++k]}`;
				else if (b === "-" && k > 0 && k < body.length - 1) cls += "-";
				else cls += b.replace(/[\]\\^-]/g, "\\$&");
			}
			out += negate ? `[^/${cls}]` : `[${cls}]`;
			i = j;
		} else if (c === "{") {
			const close = closingBrace(pattern, i);
			if (close < 0) {
				out += "\\{";
				continue;
			}
			out += `(?:${alternatives(pattern.slice(i + 1, close)).map(compile).join("|")})`;
			i = close;
		} else {
			out += escapeChar(c);
		}
	}
	return out;
}

/** Returns a predicate that tests a relative POSIX path against `pattern`. */
export function globMatcher(pattern: string): (path: string) => boolean {
	let negations = 0;
	while (pattern[negations] === "!") negations++;
	const regex = new RegExp(`^${compile(pattern.slice(negations))}$`, "s");
	const negate = negations % 2 === 1;
	return (path) => regex.test(path) !== negate;
}
