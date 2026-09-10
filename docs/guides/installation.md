# Installation

[Documentation](../index.md) · [English](../../README.md) · [한국어](../../README.ko.md) · [MIT License](../../LICENSE)

Harness configures an existing coding-agent workstation. It does not install OMP, Herdr, Antigravity CLI, model credentials, or all third-party skills. Commands below run from the repository root unless stated otherwise.

## Recommended environment and compatibility

| Component | Maintained showcase target |
| --- | --- |
| Operating environment | Linux or WSL2 with Bash 4+ and GNU-compatible utilities (`readlink -f`, `cmp`, `cp`, `ln`). Native Windows and macOS installation are not maintained targets. |
| OMP | A stock `@oh-my-pi/pi-coding-agent` installation available as `omp` on `PATH`. Harness does not require a custom OMP build or runtime patch. Review future OMP releases before adopting them; this guide does not promise blanket compatibility. |
| Bun | **1.3.14**. The installer, extensions, and helper CLIs use Bun; other releases are not maintained compatibility targets. |
| Python 3 | Required for `omp/config.apply.sh`, benchmarks, and selected skill collectors. |
| Existing personal instructions | `~/.claude/CLAUDE.md` must already be a file you maintain. The installer links it into AGY's global rules. The repository's `CLAUDE.md` is a separate owner-maintenance adapter. |
| Optional integrations | Install and authenticate Herdr and AGY before using their commands. Windows Chrome and the daily-report drafting workflow have separate prerequisites. |

See [recorded compatibility evidence](../FACTS.md). This is a recommended personal setup, not a compatibility or support commitment.

## Review before installation

```bash
git clone https://github.com/huketo/harness.git
cd harness
bash install.sh --help
bash install.sh --dry-run
```

Read [install.sh](../../install.sh) and [config.apply.sh](../../omp/config.apply.sh) before running mutating commands. Inspect the Herdr configuration and AGY plugin rules as part of the proposed links. `--dry-run` reports planned links, backups, conflicts, and exact-owned retired-link cleanup without changing them. A missing personal instruction file or ownership conflict can make the plan exit nonzero.

The installer is not transactional. It can create links before discovering a later conflict. Resolve each reported path issue deliberately; a failed run does not imply that nothing changed.

## Install and verify

After reviewing and accepting the workstation changes:

```bash
bash install.sh
bash omp/config.apply.sh --check
```

Restart every OMP process that was already loaded after installation. A running process can retain extensions or settings loaded before the update.

The settings check is read-only: exit `1` means managed values differ, not necessarily an installation failure. Keep your settings, or inspect the differences and explicitly apply the repository's personal policy:

```bash
bash install.sh --with-config
bash omp/config.apply.sh --check
```

`--with-config` changes managed OMP settings, including model roles, fallback policy, skill discovery, compaction policy, and `dev.autoqaConsent`. It is not required merely to link extensions. Provider credentials and model access remain with their owning tools. The model choices are personal defaults, not universally available or benchmark-proven optima.

Managed compaction sets all six policy keys: `compaction.enabled` to `true`, `compaction.methodOrder` to `remote → handoff → soft`, `compaction.keepRecentTokens` to `40000`, `compaction.thresholdPercent` to `75`, `compaction.thresholdTokens` to `-1`, and `compaction.handoffSaveToDisk` to `true`. Configuration application writes these stock OMP settings directly; `--check` only reports settings drift. Save active work before applying the policy, then restart existing OMP processes. See [built-in compaction behavior](usage.md#내장-자동-압축).

Ensure `~/.local/bin` is on `PATH`, then inspect the local commands without starting an agent:

```bash
omp-profile list
harness-run --help
```

## What changes

| Source | Destination or effect |
| --- | --- |
| `skills/*` | Per-skill links in `~/.agents/skills/` and `~/.claude/skills/`. |
| `herdr/config.toml`, selected scripts, and usagebar config | Links under `~/.config/herdr/`; inspect keybindings and helper behavior first. |
| `omp/extensions/{profiles,herdr}` | Two links, `harness-profiles` and `harness-herdr`, under `~/.omp/agent/extensions/`. |
| Retired extension links | Existing `harness-accounts` and `harness-native-compaction` links are removed only when they are owned by this checkout. Foreign or unexpected entries remain conflicts. |
| `omp/profiles.ts`, `herdr/scripts/harness-run.ts` | `~/.local/bin/omp-profile` and `~/.local/bin/harness-run`. |
| `agy/config/plugins/harness/` | Plugin link under `~/.gemini/config/plugins/`. Shared skills and existing personal instructions are linked into AGY's global slots. |
| `--with-config` only | Applies managed values through `omp config set`; it does not copy the example snapshot over live configuration. |

Existing regular configuration files receive a `.bak` copy before replacement. A differing existing backup, external symlink, real skill directory, or foreign retired-extension entry is a conflict, not permission to overwrite or remove it. Correct links are left unchanged. Dry-run performs no cleanup. See [ownership rules](../REPO.md).

The retirement cleanup does not delete or rewrite OMP authentication, saved preferences, session transcripts, or backups. The accounts extension's shared preference is no longer applied, and account choice is now manual and session-local through OMP's built-in `/session pin`. Legacy Harness native-compaction replay and portable migration are removed. A transcript can remain on disk without being resumable when it depends on that legacy state.

The installer does **not** restore cron jobs, copy AGY settings, install plugin repositories, provision credentials, publish Git changes, or submit reports. The distributed cron snapshot is intentionally empty (`version: 1`, `jobs: []`). Example snapshots are review aids, not host restore inputs.

## External skills and plugins

- Repository-owned and adopted skills are linked by `install.sh`. Provenance and retained licenses are recorded in [adopted-skills.json](../../third-party/adopted-skills.json) and component license files.
- [skills.lock.json](../../third-party/skills.lock.json) is a comparison snapshot of publicly available manager-owned skills, not a portable lockfile with a verified bulk restore command. Install only what you choose to trust.
- [plugins.manifest.json](../../herdr/plugins.manifest.json) records public plugin repositories and pinned references. Review each license and prerequisite before installing it with its owning tool.
- The browser CLI and its external skill are installed separately when needed:

```bash
npm install -g @playwright/cli@latest
npx skills add microsoft/playwright-cli --skill playwright-cli --global --agent universal --agent claude-code -y
```

The `latest` example is not a reproducible version pin. Review the selected release and let the skill manager own its local lock state.

### Diagram skill migration

`diagram-design` replaces the repository-owned `svg-diagram` skill. It retains the upstream type references, semantic patterns, examples, and import/export workflows, while adding local document and mobile guidance. The existing installer discovers the new skill through `skills/*`; no separate plugin installation is required.

The installer does not automatically prune retired skill links. Before an approved installation, inspect `~/.agents/skills/svg-diagram` and `~/.claude/skills/svg-diagram` with `readlink -f`, or plain `readlink` for a dangling chain. Remove only symlinks that still point to this checkout's retired `skills/svg-diagram`, including a Claude link routed through `~/.agents/skills`. Remove the Claude link first so that the chain remains inspectable. Preserve regular directories, external links, and user-modified copies, and resolve them separately. Do not leave both skills discoverable. Then run the normal installation steps and start a new agent session so it loads the current skill list.

Repository adoption does not apply these host changes automatically. See the [diagram usage guide](usage.md#다이어그램과-문서-양식) for the local gallery, document artifacts, and mobile verification boundary.

## Updating and undoing

The checkout is the live source for installed symlinks: edits and repository updates immediately affect linked assets. Review changes before updating an installed checkout. After an update, rerun dry-run and installation, then restart OMP. Review compatibility deliberately before changing OMP or Bun versions.

There is no automated uninstaller. Inspect each installed link and remove only links still pointing into this checkout; restore matching `.bak` files where appropriate. Settings applied with `--with-config` require deliberate rollback; removing links does not undo them. Keep credentials, manager-owned skills, transcripts, backups, and unrelated configuration intact. If an older Harness release patched OMP, reinstall stock OMP through its original package manager rather than restoring an old backup over a different version; the current installer does not alter those backups.
