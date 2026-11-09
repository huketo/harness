---
status: accepted
---

# Node.js, TypeScript, mise, changesets, and rulesync

Harness configures three agents (Claude Code, Codex, Antigravity CLI) from one policy and ships a versioned plugin. It now runs on Node.js with TypeScript executed by Node's built-in type stripping, pins Node and rulesync with mise, versions releases with changesets, and generates the Claude Code and Antigravity CLI credential denies with rulesync. Hooks are not generated: the merge guard ships in the plugin with a per-agent `--format`, and Codex keeps its execpolicy rules because rulesync's Codex output replaces the sandbox profile. `mise run install` replaces `install.sh` as the only installation entry point.

Node was chosen over Bun because rulesync supports only Node (`engines.node >=22.22.0`) and because Node is the more widely available runtime; hook start-up costs about 20 ms on Node against about 10 ms on Bun, which does not matter for a per-command guard. Code uses only syntax that type stripping can erase, so there is no build step and `enum` or parameter properties are not allowed.

rulesync is the generation engine, wrapped by a repository script rather than replaced, because it already maps one source onto several agents but owns whole permission categories. `scripts/safe-generate.ts` therefore runs it in a throwaway `HOME` seeded with copies of the real settings, puts back array entries it dropped, refuses any other loss, writes Claude files under `CLAUDE_CONFIG_DIR`, and keeps backups.

## Considered options

- Stay on Bun: faster start-up and the existing code, but rulesync would run on an unsupported runtime.
- Write an in-house normalizer with rulesync's scope: full control, but it duplicates a maintained tool.
- Extract the wrapper scripts into a standalone CLI now: deferred until someone else wants to use them, more than three agents need support, or the parts rulesync cannot absorb keep growing.
