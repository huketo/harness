// Updates the checkout that owns this script, then reinstalls (`mise run update`).
//   node scripts/update.ts [--dry-run] [--skills-only]
// Only a clean `main` is updated, and only by fast-forward from origin/main; review branches, detached pins, local
// work, and divergent histories are left as they are. --dry-run fetches and lists incoming commits, nothing more.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = dirname(dirname(fileURLToPath(import.meta.url)));

function git(repo: string, args: string[], inherit = false): { status: number; out: string } {
	const run = spawnSync("git", ["-C", repo, ...args], { encoding: "utf8", stdio: ["ignore", inherit ? "inherit" : "pipe", "inherit"] });
	return { status: run.status ?? 1, out: (run.stdout ?? "").trim() };
}

export async function update(args: string[], repo = REPO, print = (line: string) => console.log(line)): Promise<number> {
	const unknown = args.filter((a) => !["--dry-run", "--skills-only"].includes(a));
	if (unknown.length) {
		print(`unknown argument: ${unknown.join(" ")}\nusage: node scripts/update.ts [--dry-run] [--skills-only]`);
		return 2;
	}
	if (git(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"]).out !== "main") {
		print("update requires main; leave review branches and detached pins unchanged");
		return 1;
	}
	if (git(repo, ["status", "--porcelain"]).out) {
		print("update requires a clean checkout; preserve and resolve local work first");
		return 1;
	}
	if (git(repo, ["fetch", "--quiet", "origin", "main"]).status !== 0) return 1;
	print(git(repo, ["log", "--oneline", "HEAD..FETCH_HEAD"]).out || "no incoming commits");
	if (args.includes("--dry-run")) {
		print("dry-run: checkout and installed assets unchanged; fetched refs only");
		return 0;
	}
	if (git(repo, ["merge", "--ff-only", "--quiet", "FETCH_HEAD"], true).status !== 0) {
		print("origin/main is not a fast-forward of this checkout; resolve it by hand");
		return 1;
	}
	// Run the installer the fast-forward just brought in, not the copy this process loaded before it.
	const installer = [join(repo, "scripts/install.ts"), "--apply", ...(args.includes("--skills-only") ? ["--skills-only"] : [])];
	return spawnSync(process.execPath, installer, { stdio: "inherit" }).status ?? 1;
}

if (import.meta.main) process.exit(await update(process.argv.slice(2)));
