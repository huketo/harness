import { join } from "node:path";

export interface RenderRequest {
	workspace: string;
	entry: string;
	widths: number[];
	schemes: ("light" | "dark")[];
	/** Directory the PNGs go to (`<run>/screens`). */
	outDir: string;
}

export interface RenderedScreen {
	width: number;
	scheme: "light" | "dark";
	/** File name inside `outDir`. */
	file: string;
	overflowPx: number;
	consoleErrors: string[];
}

export type RenderOutcome =
	| { ok: true; screens: RenderedScreen[]; blockedRequests: string[] }
	/** The browser could not be used; the check becomes `pass: null`. */
	| { ok: false; error: string };

export type Renderer = (request: RenderRequest) => Promise<RenderOutcome>;

export const RENDER_SCRIPT = join(import.meta.dir, "render.py");

/** Renders with `uv run --with playwright python3 render.py`, the repository's Playwright convention. */
export const playwrightRenderer: Renderer = async (request) => {
	const uv = Bun.which("uv");
	if (!uv) return { ok: false, error: "uv is not installed" };
	const child = Bun.spawn(
		[
			uv,
			"run",
			"--no-project",
			"--quiet",
			"--with",
			"playwright",
			"python3",
			RENDER_SCRIPT,
			"--workspace",
			request.workspace,
			"--entry",
			request.entry,
			"--widths",
			request.widths.join(","),
			"--schemes",
			request.schemes.join(","),
			"--out",
			request.outDir,
		],
		{ stdin: "ignore", stdout: "pipe", stderr: "pipe" },
	);
	const [stdout, stderr, code] = await Promise.all([
		new Response(child.stdout).text(),
		new Response(child.stderr).text(),
		child.exited,
	]);
	const line = stdout.trim().split("\n").at(-1) ?? "";
	try {
		const parsed = JSON.parse(line) as RenderOutcome;
		if (parsed.ok && code === 0) return parsed;
		if (!parsed.ok) return parsed;
	} catch {}
	const tail = stderr.trim().split("\n").slice(-3).join(" | ");
	return { ok: false, error: `render.py exited with ${code}: ${tail || "no output"}` };
};
