// Property: harness-mode (bash) and the merge guard (JavaScript) read the full-send allowlist the same way.
// Covers repo_key() and allowed() in skills/full-send/scripts/harness-mode, and repoKey(), parseAllowlist(), and
// allowedRepo() in merge-guard.mjs. If the two disagree, a mode can be recorded as full-send where the hook then
// denies the merge, or the other way round. Inputs are generated remote URLs and allowlist lines in the forms
// docs/AGENT-CONFIG.md lists; the seed is fixed so a failure reproduces.
//   node --test plugin/hooks/allowlist.property.test.mjs
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import fc from "fast-check";
import { allowedRepo, parseAllowlist, repoKey } from "./merge-guard.mjs";

const MODE = join(import.meta.dirname, "../../skills/full-send/scripts/harness-mode");
let root, repo, env;

before(() => {
	root = mkdtempSync(join(tmpdir(), "allowlist-property-"));
	repo = join(root, "repo");
	mkdirSync(join(root, "config/harness"), { recursive: true });
	env = { ...process.env, HOME: join(root, "home"), XDG_CONFIG_HOME: join(root, "config"), GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" };
	execFileSync("git", ["init", "-q", repo], { env });
	execFileSync("git", ["-C", repo, "remote", "add", "origin", "https://placeholder.example/a/b.git"], { env });
});
after(() => rmSync(root, { recursive: true, force: true }));

const word = fc.stringMatching(/^[A-Za-z0-9][A-Za-z0-9_-]{0,7}$/);
const host = fc.tuple(word, fc.constantFrom("com", "example", "net")).map(([name, tld]) => `${name}.${tld}`);
const path = fc.array(word, { minLength: 2, maxLength: 3 }).map((parts) => parts.join("/"));
const remote = fc.tuple(host, path, fc.constantFrom("https", "ssh-port", "scp", "plain"), fc.boolean()).map(([h, p, form, git]) => {
	const tail = `${p}${git ? ".git" : ""}`;
	if (form === "https") return `https://${h}/${tail}`;
	if (form === "ssh-port") return `ssh://git@${h}:2222/${tail}`;
	if (form === "scp") return `git@${h}:${tail}`;
	return `${h}/${tail}`;
});
// An allowlist line: an exact repository, an owner prefix, or noise, drawn near the origin so matches are common.
const line = (h, p) =>
	fc.oneof(
		fc.constantFrom(`${h}/${p}`, `${h}/${p}.git`, `${h}/${p.split("/")[0]}/*`, `${h.toUpperCase()}/${p}`, `${h}/${p}/*`, `${h}/*`, `  ${h}/${p}  # note`, `# ${h}/${p}`, ""),
		fc.tuple(host, path).map(([otherHost, otherPath]) => `${otherHost}/${otherPath}`),
		fc.tuple(host, word).map(([otherHost, owner]) => `${otherHost}/${owner}/*`),
	);
const scenario = fc.tuple(host, path).chain(([h, p]) =>
	fc.record({ origin: fc.oneof(remote, fc.constantFrom(`https://${h}/${p}.git`, `git@${h}:${p}.git`, `ssh://git@${h}:2222/${p}`)), lines: fc.array(line(h, p), { maxLength: 4 }) }),
);

test("harness-mode and the merge guard agree on whether a repository is allowlisted", () => {
	fc.assert(
		fc.property(scenario, ({ origin, lines }) => {
			const text = `${lines.join("\n")}\n`;
			writeFileSync(join(root, "config/harness/full-send-repos"), text);
			execFileSync("git", ["-C", repo, "remote", "set-url", "origin", origin], { env });
			const shell = spawnSync(MODE, ["allowlist"], { cwd: repo, encoding: "utf8", env }).stdout.startsWith("allowed:");
			assert.equal(shell, allowedRepo(repoKey(origin), parseAllowlist(text)), `origin ${origin}\nallowlist:\n${text}`);
		}),
		{ seed: 20261118, numRuns: 200 },
	);
});
