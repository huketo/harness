# Installation

[Documentation](../index.md) · [English](../../README.md) · [한국어](../../README.ko.md) · [MIT License](../../LICENSE)

Harness configures an existing coding-agent workstation. It does not install T3 Code, Claude Code, Codex CLI, Antigravity CLI, Herdr, model credentials, or all third-party skills. Commands below run from the repository root unless stated otherwise.

## Recommended environment and compatibility

| Component | Maintained showcase target |
| --- | --- |
| Operating environment | Linux or WSL2 with Bash 4+ and GNU-compatible utilities (`readlink -f`, `cmp`, `cp`, `ln`). Native Windows and macOS installation are not maintained targets. |
| Agent CLIs | Claude Code, Codex CLI, and Antigravity CLI (`agy`), installed and authenticated separately. [T3 Code](https://github.com/pingdotgg/t3code) runs them as threads. Review future releases before adopting them; this guide does not promise blanket compatibility. |
| mise | Required. [`mise.toml`](../../mise.toml) pins **Node.js 24.22.2** and **rulesync 43.8.0**, and defines every entry point (`mise run plan`, `install`, `update`, `check`). Run `mise trust && mise install` once per checkout. Node runs the installer, the merge-guard hook, the T3 scheduled-task guard, host sync, and the Codex reviewer (`codex/review.ts`); other versions are not maintained compatibility targets. |
| Python 3 | Required for the cost-audit analyzer and selected skill collectors. |
| Existing personal instructions | Optional. When `<Claude config dir>/CLAUDE.md` exists, the installer links it into AGY's global rules; otherwise that step is skipped. The repository's `CLAUDE.md` is a separate owner-maintenance adapter. |
| Claude Code config directory | `CLAUDE_CONFIG_DIR` when it is set, otherwise `~/.claude`. Skills, settings, and the credentials deny follow it. |
| Optional integrations | Install [Herdr](https://github.com/herdrdev/herdr) before using `t3-terminal`; the skill drives it as a plain terminal multiplexer, and the installer does not configure it. BrowserSkill and the daily-report drafting workflow have separate prerequisites. |

See [recorded compatibility evidence](../FACTS.md). This is a recommended personal setup, not a compatibility or support commitment.

## Review before installation

```bash
git clone https://github.com/huketo/harness.git
cd harness
mise trust && mise install
mise run plan
```

Read [scripts/install.ts](../../scripts/install.ts), [scripts/links.ts](../../scripts/links.ts), [scripts/safe-generate.ts](../../scripts/safe-generate.ts), and [plugin/install.mjs](../../plugin/install.mjs) before running mutating commands, and inspect the plugin sources under `plugin/` and the deny rules in [`.rulesync/permissions.jsonc`](../../.rulesync/permissions.jsonc) as part of the proposed changes. `mise run plan` reports planned links, backups, permission changes, plugin steps, and conflicts without changing anything; it exits nonzero when a step needs a person.

The installer is not transactional. It can create links before discovering a later conflict. Resolve each reported path issue deliberately; a failed run does not imply that nothing changed.

### Shared machines: skills only

Use `node scripts/install.ts --skills-only` to review, then
`node scripts/install.ts --skills-only --apply` to link only `skills/*` into the two skill
directories. This mode leaves AGY slots, Codex rules, plugins, and agent settings unchanged. Existing foreign skill
names remain ownership conflicts; the installer does not rename or overwrite them.

Keep the clone at a stable path because the installed skills point into it.
Compare its skill directory names with the other tool's installed names before
installation. A pin or lock snapshot does not install manager-owned skills.

## Install and verify

After reviewing and accepting the workstation changes:

```bash
mise run install
mise run plan
```

The second command should report every step as unchanged: the installer is idempotent. Start new agent sessions or T3 threads after installation so they discover the current skill list; a running session does not reload it retroactively.

## What changes

| Source | Destination or effect |
| --- | --- |
| `skills/*` | Per-skill links in `~/.agents/skills/` and `<Claude config dir>/skills/`. |
| AGY slots | `~/.gemini/config/skills` links to `~/.agents/skills`, and `~/.gemini/config/rules/AGENTS.md` links to `<Claude config dir>/CLAUDE.md` when that file exists. An existing entry in either slot is a conflict. |
| `codex/harness.rules` | Link at `~/.codex/rules/harness.rules`. Codex asks before the `gh` and `glab` merge commands, and refuses them under `approval_policy = "never"`. |
| `.rulesync/permissions.jsonc` (through `scripts/safe-generate.ts`) | Credential-read deny rules merged into `<Claude config dir>/settings.json` and `~/.gemini/antigravity-cli/settings.json`, for each agent whose config directory exists. rulesync runs in a throwaway `HOME`; every existing setting is kept, and a change that would still drop one is refused as a conflict. Each replaced file keeps a `<file>.hstack-bak-<time>` copy and its file mode; a symlinked settings file is written through to its target so the link stays, and a file that changes between plan and apply is refused. Codex permissions are not generated, because rulesync's Codex output replaces Codex's sandbox profile; see [AGENT-CONFIG](../AGENT-CONFIG.md). |
| `plugin/` (through `plugin/install.mjs`) | When `claude` is on `PATH`, registers this repository's GitHub marketplace as `hstack`, installs `hstack@hstack` at user scope, and turns marketplace auto-update on unless you set it. When `agy` is on `PATH`, builds an AGY plugin copy under `${XDG_STATE_HOME:-~/.local/state}/hstack/plugins/agy` and installs it with `agy plugin install`, because AGY skips symlinked plugin directories. [plugin-release.md](plugin-release.md) explains how a new plugin version reaches Claude Code. |

Existing regular configuration files receive a `.bak` copy before replacement with a link. A differing existing backup, external symlink, or real skill directory is a conflict, not permission to overwrite it. Correct links are left unchanged. Links that earlier installer versions created for components now in [`archived/`](../../archived/) are neither refreshed nor removed; see [Updating and undoing](#updating-and-undoing). See [ownership rules](../REPO.md).

The installer does **not** create or enable T3 scheduled tasks, copy AGY settings (it only adds deny rules), install agent CLIs or Herdr, write the `full-send` allowlist, provision credentials, publish Git changes, or submit reports. The distributed `t3/scheduled/jobs.json` is intentionally empty (`version: 1`, `jobs: []`). Example snapshots are review aids, not host restore inputs.

Every step prints one line in the same `would …`, `unchanged …`, `skipped: …`, and `conflict: …` form. A Claude marketplace or AGY plugin named `hstack` that this checkout did not ship, or a settings file that is not valid JSON, is reported as a conflict and left unchanged. Remove the plugin with `claude plugin uninstall hstack@hstack` and `agy plugin uninstall hstack`; deny rules added to settings files stay until you remove them, and the `.hstack-bak-<time>` copy holds the file before each change.

### Moving from the `harness` plugin

Earlier versions installed the same plugin as `harness@harness` from a directory marketplace under `${XDG_STATE_HOME:-~/.local/state}/harness/plugins/claude`, and the AGY copy as `harness`. The installer reports such a leftover as `skipped: legacy …` with the command that removes it, and does not remove it itself, because removing a marketplace uninstalls its plugin at every scope. Until it is removed both plugins load, so the merge guard runs twice and the reviewer exists under both names. Remove it with `claude plugin marketplace remove harness` and `agy plugin uninstall harness`.

## External skills and plugins

- Repository-owned and adopted skills are linked by `mise run install`. Provenance and retained licenses are recorded in [adopted-skills.json](../../third-party/adopted-skills.json) and component license files.
- [skills.lock.json](../../third-party/skills.lock.json) is a comparison snapshot of publicly available manager-owned skills, not a portable lockfile with a verified bulk restore command. Install only what you choose to trust.
- BrowserSkill is an external CLI and manager-owned skill. On WSL2, install the Linux CLI in WSL and the extension in Windows Chrome:

```bash
curl -fsSL https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.sh | sh
export PATH="${BSK_INSTALL_DIR:-$HOME/.local/bin}:$PATH"
bsk install-skill --harness codex --json
bsk install-skill --harness claude-code --json
bsk doctor
```

  Follow the [upstream agent install guide](https://github.com/Tencent/BrowserSkill/blob/main/AGENT_INSTALL.md). The `codex` target writes `~/.agents/skills/browser-skill`, which Codex and AGY discover; `claude-code` writes its own managed copy. Do not copy either installation into this repository. Install the extension from its official store in Windows Chrome, select **Local connection**, and match the WSL daemon port (default `52800`). This path needs no `sudo`, Windows Node.js, CDP relay, firewall rule, or dedicated Chrome profile.
- Playwright CLI remains an independent fallback for isolated automation:

```bash
npm install -g @playwright/cli@latest
npx skills add microsoft/playwright-cli --skill playwright-cli --global --agent universal --agent claude-code -y
```

The unpinned examples are not reproducible pins. Review the selected releases and let each owning installer manage its local state.


### BrowserSkill migration

`browser-skill` replaces the repository-owned `windows-chrome` skill for visible, logged-in Windows Chrome work from WSL2. Before removing the old source, inspect `~/.agents/skills/windows-chrome` and `~/.claude/skills/windows-chrome` with `readlink` and remove only symlinks that still route to this checkout's retired `skills/windows-chrome`. Remove the Claude link first. Preserve regular directories, external links, the old dedicated Chrome profile, and unrelated runtime state. Install BrowserSkill through `bsk`, run `bsk doctor`, verify a page in a stopped test session, and start a new agent session so the managed skill is discovered.

### Diagram skill migration

`diagram-design` replaces the repository-owned `svg-diagram` skill. It retains the upstream type references, semantic patterns, examples, and import/export workflows, while adding local document and mobile guidance. The existing installer discovers the new skill through `skills/*`; no separate plugin installation is required.

The installer does not automatically prune retired skill links. Before an approved installation, inspect `~/.agents/skills/svg-diagram` and `~/.claude/skills/svg-diagram` with `readlink -f`, or plain `readlink` for a dangling chain. Remove only symlinks that still point to this checkout's retired `skills/svg-diagram`, including a Claude link routed through `~/.agents/skills`. Remove the Claude link first so that the chain remains inspectable. Preserve regular directories, external links, and user-modified copies, and resolve them separately. Do not leave both skills discoverable. Then run the normal installation steps and start a new agent session so it loads the current skill list.

Repository adoption does not apply these host changes automatically. See the [diagram usage guide](usage.md#다이어그램과-문서-양식) for the local gallery, document artifacts, and mobile verification boundary.

## Updating and undoing

The checkout is the live source for installed symlinks: edits and repository updates immediately affect linked assets. Review changes before updating an installed checkout. After an update, rerun `mise run plan` and installation, then start new agent sessions. Review compatibility deliberately before changing agent CLI, Node, or rulesync versions.

For a clean `main` clone tracking the public repository, update with:

```bash
mise run update -- --dry-run
mise run update
```

`scripts/update.ts` requires `main` and a clean worktree,
runs `git fetch origin main` and lists the incoming commits, then fast-forwards and
runs the freshly fetched installer with `--apply` (`--skills-only` is passed through).
`--dry-run` fetches and shows commits without changing the checkout or installed
assets. A topic branch, detached revision, dirty checkout, or divergent history
is not switched, stashed, rebased, combined with a merge commit, or reset.
Review the dry-run before updating: fast-forwarding changes live symlink targets
before reinstallation, and an installation conflict does not roll back that fast-forward.

For a fixed release pin, keep the clone detached on a release tag (`v<version>`) and deliberately select the next
reviewed release, then rerun `mise run install`. The updater
does not advance detached pins. Neither update mode installs agent CLIs or external
skills, or changes another tool's installation.

There is no automated uninstaller. Inspect each installed link and remove only links still pointing into this checkout; restore matching `.bak` files where appropriate. Deny rules merged into agent settings and plugin registrations require deliberate rollback; removing links does not undo them, and each `.hstack-bak-<time>` copy records a settings file before one change (older installs left a one-time `.harness-bak`). Keep credentials, manager-owned skills, transcripts, backups, and unrelated configuration intact.

Links left by earlier installer versions for components now in [`archived/`](../../archived/), such as entries under `~/.omp/agent/extensions/` and `~/.config/herdr/` and the `omp-profile` and `harness-run` launchers in `~/.local/bin/`, are cleaned up the same way: inspect each with `readlink -f` and remove only links that still resolve into this checkout. Because those sources moved, such links now dangle. Earlier settings applied through the removed `--with-config` option are not rolled back by removing links.
