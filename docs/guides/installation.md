# Installation

[Documentation](../index.md) · [English](../../README.md) · [한국어](../../README.ko.md) · [MIT License](../../LICENSE)

Harness configures an existing coding-agent workstation. It does not install OMP, Herdr, Antigravity CLI, model credentials, or all third-party skills. Commands below run from the repository root unless stated otherwise.

## Recommended environment and compatibility

| Component | Maintained showcase target |
| --- | --- |
| Operating environment | Linux or WSL2 with Bash 4+ and GNU-compatible utilities (`readlink -f`, `cmp`, `cp`, `ln`). Native Windows and macOS installation are not maintained targets. |
| OMP | `@oh-my-pi/pi-coding-agent` **18.1.13**, available as `omp` on `PATH`. The runtime patch rejects other versions or unexpected source layouts. |
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

Read [install.sh](../../install.sh), [native-runtime.ts](../../omp/native-runtime.ts), and [config.apply.sh](../../omp/config.apply.sh) before running mutating commands. Inspect the Herdr configuration and AGY plugin rules as part of the proposed links. `--dry-run` shows the plan but does **not** prove that the installed OMP source is patch-compatible. A missing personal instruction file or ownership conflict can make the plan exit nonzero.

The installer is not transactional. It can create links before discovering a later conflict or incompatible OMP installation. Resolve each reported path or version issue deliberately; a failed run does not imply that nothing changed.

## Install and verify

After reviewing and accepting the workstation changes:

```bash
bash install.sh
bun omp/native-runtime.ts --check
bash omp/config.apply.sh --check
```

Restart running OMP processes after installation. Reloading extensions alone does not reload the patched CLI runtime.

The settings check is read-only: exit `1` means managed values differ, not necessarily an installation failure. Keep your settings, or inspect the differences and explicitly apply the repository's personal policy:

```bash
bash install.sh --with-config
bash omp/config.apply.sh --check
```

`--with-config` changes managed OMP settings, including model roles, fallback policy, skill discovery, compaction policy, and `dev.autoqaConsent`. It is not required merely to link extensions. Provider credentials and model access remain with their owning tools. The model choices are personal defaults, not universally available or benchmark-proven optima.

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
| `omp/extensions/{accounts,profiles,herdr,native-compaction}` | Four `harness-*` links under `~/.omp/agent/extensions/`. |
| `omp/profiles.ts`, `herdr/scripts/harness-run.ts` | `~/.local/bin/omp-profile` and `~/.local/bin/harness-run`. |
| `agy/config/plugins/harness/` | Plugin link under `~/.gemini/config/plugins/`. Shared skills and existing personal instructions are linked into AGY's global slots. |
| `omp/native-runtime.ts` | Patches the installed OMP CLI bundle and SDK source files for native compaction. Originals remain beside them as `.harness-native-original`. |
| `--with-config` only | Applies managed values through `omp config set`; it does not copy the example snapshot over live configuration. |

Existing regular configuration files receive a `.bak` copy before replacement. A differing existing backup, external symlink, or real skill directory is a conflict, not permission to overwrite it. Correct links are left unchanged. See [ownership rules](../REPO.md).

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

## Updating and undoing

The checkout is the live source for installed symlinks: edits and repository updates immediately affect linked assets. Review changes before updating an installed checkout. After an update, rerun dry-run, installation, the runtime check, and the OMP restart. Revalidate before changing OMP or Bun versions.

There is no automated uninstaller. Inspect each installed link and remove only links still pointing into this checkout; restore matching `.bak` files where appropriate. Restore `.harness-native-original` files only to the same OMP installation, or reinstall OMP through its original package manager. Do not restore old backups over a newer OMP version. Settings applied with `--with-config` require deliberate rollback; removing links does not undo them. Keep credentials, manager-owned skills, and unrelated configuration intact.
