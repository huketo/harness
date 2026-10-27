# Harness

[English](README.md) · [한국어](README.ko.md)

**A version-controlled personal workstation setup for coding agents: shared skills, T3 Code integration, guardrails, and guarded automation.**

Harness configures an existing [T3 Code](https://github.com/pingdotgg/t3code) workstation whose agents run as threads on Claude Code, Codex CLI, and Antigravity CLI (`agy`). It is a personal configuration and extension showcase, not a standalone agent, a hosted service, or a replacement for those tools. [Herdr](https://github.com/herdrdev/herdr) stays only as a plain terminal multiplexer for terminal work a person watches. Retired Herdr agent-runtime, Oh My Pi, and benchmark sources are frozen in [`archived/`](archived/); nothing installs or runs them.

[Installation](docs/guides/installation.md) · [Documentation](docs/index.md) · [Usage](docs/guides/usage.md) · [Reuse policy](CONTRIBUTING.md) · [MIT License](LICENSE)

## What it adds

| Capability | What you get |
| --- | --- |
| Shared skills | Repository-owned instructions linked into Claude Code, Codex, and AGY, with retained notices for adopted material. |
| UI design workflows | Four focused skills for interface design/review, image-to-web implementation, UI/brand reference-image generation, and optional design-system documentation; no mandatory image or document pipeline. See [usage](docs/guides/usage.md). |
| T3 Code path | `t3-orchestrate`, `review-loop`, and `council` delegate through T3's orchestration tools; `t3-handoff` continues the work in a new thread from a handoff document; [T3 human-in-the-loop rules](docs/agents/hitl.md) route questions through the thread; `codex/review.ts` runs an independent review in Codex's read-only sandbox outside T3 (inside T3 the Codex reviewer is a `delegate_task` child); `t3/scheduled/guard.mjs` adds timeouts and run limits to scheduled tasks. |
| Watched terminal work | `t3-terminal` opens Herdr workspaces, tabs, and panes for dev servers, interactive prompts, REPLs, ssh, and TUIs that a person must watch or step into. It is not a substitute for background processes. |
| Interactive visuals | `t3-show` builds explorable views inside the thread with `html_render`: codebase maps, algorithm steppers, assumption-driven simulations such as GTM metrics, and data exploration. Each page is grounded in code read or numbers computed in the shell, self-checks against them, and is driven through its interactions in `html_preview` before it is shown. |
| MR lifecycle and work modes | GitLab MR and GitHub PR skills adapted from tstack (`file-mr`, `babysit-mr`, `leaving-mr-comments`, `takeover`, `modernize`) and the user-selected `full-send`/`full-stop` modes. A merge-guard hook in the `plugin/` artifacts for Claude Code and AGY, and `codex/harness.rules` for Codex, block merges the mode does not allow; `full-send` merges only in repositories you list in an allowlist. See [AGENT-CONFIG](docs/AGENT-CONFIG.md). |
| Personal operations | Cost audits over Claude Code and Codex sessions, guarded host synchronization, and a human-reviewed daily-report drafting workflow. These are not hosted services. |

## Recommended environment

The maintained showcase target is **Linux or WSL2 with Bash, GNU-compatible utilities, and Bun 1.3.14**. Node.js is needed for the full installation's plugin step, Bun for the scheduled-task guard, host sync, and the Codex reviewer, and Python 3 for the cost-audit analyzer and skill collectors. An existing `~/.claude/CLAUDE.md` is required by the current installer. Install and authenticate T3 Code, Claude Code, Codex CLI, and AGY separately. Native Windows and macOS are not maintained installation targets. Future agent CLI or Bun releases must be reviewed rather than assumed compatible.

```bash
git clone https://github.com/huketo/harness.git
cd harness
bash install.sh --dry-run
```

Review the [installation guide](docs/guides/installation.md), the source, and the proposed workstation changes before proceeding.

```bash
bash install.sh
```

**Installation changes your workstation:** it links shared assets, backs up eligible existing configuration files, installs the `harness` plugin into Claude Code and AGY when they are on `PATH`, adds credential-read deny rules to their settings files, and links a Codex execpolicy file. A foreign or unexpected entry remains a conflict and is not removed; dry-run reports the plan without mutating it. Start new agent sessions afterwards so they load the current skills. Links that earlier installer versions created for components now in `archived/` are not removed; see [manual rollback boundaries](docs/guides/installation.md#updating-and-undoing). AGY settings and T3 scheduled tasks are not restored by the installer.

On a shared workstation, `bash install.sh --skills-only` links only skills and
leaves tool configuration and commands unchanged. Keep the clone at a stable
path; `bash /path/to/harness/update.sh --skills-only` fast-forwards a clean `main`
clone and reinstalls. Review updates first because installed links are live.
See [installation and update boundaries](docs/guides/installation.md).

## Everyday use

Agents run as T3 Code threads. In a thread, `t3-orchestrate` splits independent work across worktree children, `review-loop` and `council` run read-only reviews by other model families, and the MR skills (`file-mr`, `babysit-mr`, `takeover`, `modernize`) carry GitLab MRs and GitHub PRs. Questions and approvals go through the thread under the [human-in-the-loop rules](docs/agents/hitl.md).

Send terminal work a person must watch or step into through `t3-terminal`; attach with `herdr` in your own terminal to watch it or type. Run short reads, builds, tests, and background processes with normal tools.

Check the boundary of the Codex reviewer used outside T3 without calling a model:

```bash
bun --no-install codex/review.ts --cwd <worktree> --inspect-tools
```

See [detailed usage and state boundaries](docs/guides/usage.md) (Korean). Dated measurements live in [FACTS](docs/FACTS.md) and pricing evidence in [PRICING](docs/PRICING.md); they are observations, not performance guarantees.

## Configuration and safety

- **One owner per asset:** hand-maintained assets are symlinked; tool-managed state stays with its owning tool. Distributed snapshots are review examples, not host backup or restore instructions.
- **Credentials stay local:** keep API keys, OAuth state, private calendar URLs, messaging tokens, session logs, and report inputs outside version control. `.gitignore` is not a secret scanner and does not erase history.
- **Review external effects:** T3 schedule activation, messages, plugin updates, remote writes, merges, and Git publication require deliberate owner action. The merge guard is a guardrail against accidental merges, not an authorization system. No distributed snapshot should be activated unchanged.
- **No sandbox claim:** permission policies and file-tool deny rules do not isolate arbitrary shell access. Treat permissive workstation settings as personal risk choices, not security defaults.
- **Live links matter:** editing or updating this checkout changes installed assets immediately. There is no automated uninstaller; [manual rollback boundaries](docs/guides/installation.md#updating-and-undoing) explain what link removal does not undo.

## Find your way around

| Path | Purpose |
| --- | --- |
| [`skills/`](skills/) | Personal skills and adopted skills with retained notices. |
| [`plugin/`](plugin/) | One source for the Claude Code and AGY plugins: merge guard, read-only reviewer agent, AGY rules, builder, installer, and deny rules. |
| [`codex/`](codex/) | Read-only Codex reviewer and the execpolicy rules that make Codex ask before merging. |
| [`t3/`](t3/) | Guard for T3 Code scheduled tasks and the guarded host sync; the distributed job list is empty. |
| [`agy/`](agy/) | An example AGY settings snapshot. |
| [`third-party/`](third-party/) | External provenance, lock snapshots, and patches. |
| [`docs/`](docs/index.md) | Installation, usage, ownership, evidence, and maintenance guidance. |
| [`archived/`](archived/) | Frozen retired sources (Herdr agent runtime, OMP, benchmark runner); nothing installs, runs, or tests them. |
| `var/` | Ignored local reports and generated state; only `.gitkeep` is tracked. |

## License, reuse, and maintenance

Harness is released under the [MIT License](LICENSE). Third-party and adopted components retain their own copyright notices and license terms; [adopted-skills.json](third-party/adopted-skills.json) records their provenance.

This repository is a personal showcase maintained only for its owner. Bug reports, feature requests, pull requests, other contributions, support requests, and vulnerability reports are not accepted. You may fork, modify, and redistribute the code under the MIT License, but no maintainer service or response is offered. See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete policy.

Coding agents enter through [AGENTS.md](AGENTS.md). The README's language switch, capability overview, quick start, and deeper-documentation layout take structural inspiration from [oh-my-hermes](https://github.com/rlaope/oh-my-hermes); its branding, artwork, implementation, and product claims are not copied.
