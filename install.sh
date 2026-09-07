#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DEST="$HOME/.agents/skills"
AGY_CONFIG="$HOME/.gemini/config"
DRY_RUN=false
WITH_CONFIG=false

usage() {
  cat <<EOF
usage: $0 [--dry-run] [--with-config]

  --dry-run      show links, backups, and replacements without changing files
  --with-config  apply omp/config.apply.sh after all links succeed
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --with-config) WITH_CONFIG=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

points_into_repo() {
  local resolved
  resolved="$(readlink -f -- "$1" 2>/dev/null || true)"
  case "$resolved" in
    "$REPO"|"$REPO"/*) return 0 ;;
    *) return 1 ;;
  esac
}

same_link() {
  [[ -L "$1" ]] || return 1
  [[ "$(readlink -f -- "$1" 2>/dev/null || true)" == "$(readlink -f -- "$2")" ]]
}

ensure_dir() {
  local dir="$1"
  if [[ -d "$dir" ]]; then
    return
  fi
  if [[ -e "$dir" || -L "$dir" ]]; then
    echo "conflict: directory required but another entry exists: $dir" >&2
    conflicts+=("$dir")
    return 1
  fi
  if $DRY_RUN; then
    echo "would create directory: $dir"
  else
    mkdir -p -- "$dir"
    echo "created directory: $dir"
  fi
}

link_skill() {
  local src="$1"
  local dest="${2:-$SKILLS_DEST}"
  local name target
  name="$(basename "$src")"
  target="$dest/$name"

  if same_link "$target" "$src"; then
    echo "unchanged skill: $name -> $src"
    return
  fi

  if [[ -L "$target" ]]; then
    if ! points_into_repo "$target"; then
      echo "skipped skill $name: links outside this repo to $(readlink -f -- "$target" 2>/dev/null || readlink -- "$target")" >&2
      conflicts+=("$target")
      return
    fi
    if $DRY_RUN; then
      echo "would refresh skill link: $target -> $src"
    else
      ln -sfn -- "$src" "$target"
      echo "refreshed skill: $target -> $src"
    fi
    return
  fi

  if [[ -e "$target" ]]; then
    echo "skipped skill $name: $target exists and is not a symlink" >&2
    conflicts+=("$target")
    return
  fi

  if $DRY_RUN; then
    echo "would link skill: $target -> $src"
  else
    ln -s -- "$src" "$target"
    echo "linked skill: $target -> $src"
  fi
}

link_dir() {
  local src="$1"
  local target="$2"
  local parent
  parent="$(dirname "$target")"

  if [[ ! -d "$src" ]]; then
    echo "error: managed source directory is missing: $src" >&2
    conflicts+=("$src")
    return
  fi
  ensure_dir "$parent" || return

  if same_link "$target" "$src"; then
    echo "unchanged asset: $target -> $src"
    return
  fi

  if [[ -L "$target" ]]; then
    if ! points_into_repo "$target"; then
      echo "skipped asset: $target links outside this repo to $(readlink -f -- "$target" 2>/dev/null || readlink -- "$target")" >&2
      conflicts+=("$target")
      return
    fi
    if $DRY_RUN; then
      echo "would refresh asset link: $target -> $src"
    else
      ln -sfn -- "$src" "$target"
      echo "refreshed asset: $target -> $src"
    fi
    return
  fi

  if [[ -e "$target" ]]; then
    echo "skipped asset: $target exists and is not a symlink" >&2
    conflicts+=("$target")
    return
  fi

  if $DRY_RUN; then
    echo "would link asset: $target -> $src"
  else
    ln -s -- "$src" "$target"
    echo "linked asset: $target -> $src"
  fi
}

# Two Antigravity customization slots point at assets this repo does not own:
# the shared skill tree and the user's Claude Code instructions. Linking the
# canonical file keeps one source of truth instead of a second copy that drifts.
link_foreign() {
  local src="$1"
  local target="$2"
  local parent
  parent="$(dirname "$target")"

  if [[ ! -e "$src" ]]; then
    echo "error: external source is missing: $src" >&2
    conflicts+=("$src")
    return
  fi
  ensure_dir "$parent" || return

  if same_link "$target" "$src"; then
    echo "unchanged asset: $target -> $src"
    return
  fi

  if [[ -e "$target" || -L "$target" ]]; then
    echo "skipped asset: $target already exists and this repo will not replace it" >&2
    conflicts+=("$target")
    return
  fi

  if $DRY_RUN; then
    echo "would link asset: $target -> $src"
  else
    ln -s -- "$src" "$target"
    echo "linked asset: $target -> $src"
  fi
}

migrate_file() {
  local src="$1"
  local target="$2"
  local parent backup
  parent="$(dirname "$target")"
  backup="$target.bak"

  if [[ ! -f "$src" ]]; then
    echo "error: managed source is missing: $src" >&2
    conflicts+=("$src")
    return
  fi
  ensure_dir "$parent" || return

  if same_link "$target" "$src"; then
    echo "unchanged asset: $target -> $src"
    return
  fi

  if [[ -L "$target" ]]; then
    if ! points_into_repo "$target"; then
      echo "skipped asset: $target links outside this repo to $(readlink -f -- "$target" 2>/dev/null || readlink -- "$target")" >&2
      conflicts+=("$target")
      return
    fi
    if $DRY_RUN; then
      echo "would refresh asset link: $target -> $src"
    else
      ln -sfn -- "$src" "$target"
      echo "refreshed asset: $target -> $src"
    fi
    return
  fi

  if [[ -e "$target" ]]; then
    if [[ ! -f "$target" ]]; then
      echo "skipped asset: $target exists and is not a regular file or symlink" >&2
      conflicts+=("$target")
      return
    fi
    if [[ -e "$backup" || -L "$backup" ]]; then
      if [[ ! -L "$backup" && -f "$backup" ]] && cmp -s -- "$target" "$backup"; then
        echo "reusing identical backup: $backup"
      else
        echo "skipped asset: backup already exists and differs: $backup" >&2
        conflicts+=("$target")
        return
      fi
    elif $DRY_RUN; then
      echo "would back up: $target -> $backup"
    else
      cp -p -- "$target" "$backup"
      echo "backed up: $target -> $backup"
    fi

    if $DRY_RUN; then
      echo "would replace with link: $target -> $src"
    else
      rm -f -- "$target"
      ln -s -- "$src" "$target"
      echo "linked asset: $target -> $src"
    fi
    return
  fi

  if $DRY_RUN; then
    echo "would link asset: $target -> $src"
  else
    ln -s -- "$src" "$target"
    echo "linked asset: $target -> $src"
  fi
}

conflicts=()

# A destination symlink into this repo would send per-skill links back into the
# source tree. This is an unsafe layout, so stop rather than writing through it.
if [[ -L "$SKILLS_DEST" ]] && points_into_repo "$SKILLS_DEST"; then
  echo "error: $SKILLS_DEST is a symlink into this repo ($(readlink -f -- "$SKILLS_DEST"))" >&2
  echo "Remove it and rerun; this script will recreate it as a real directory." >&2
  exit 1
fi
if ensure_dir "$SKILLS_DEST"; then
  shopt -s nullglob
  for skill_md in "$REPO"/skills/*/SKILL.md; do
    link_skill "$(dirname "$skill_md")"
  done
  shopt -u nullglob
fi

# Claude Code reads `$HOME/.claude/skills`, not `$HOME/.agents/skills`, so a
# repo-owned skill is invisible to it without its own link. The `skills` CLI
# already fills that directory this way for the skills it installs, and the
# link resolves through `$SKILLS_DEST` so it still points into this repo.
if ensure_dir "$HOME/.claude/skills"; then
  shopt -s nullglob
  for skill_md in "$REPO"/skills/*/SKILL.md; do
    link_skill "$SKILLS_DEST/$(basename "$(dirname "$skill_md")")" "$HOME/.claude/skills"
  done
  shopt -u nullglob
fi

migrate_file "$REPO/herdr/config.toml" "$HOME/.config/herdr/config.toml"
migrate_file "$REPO/herdr/scripts/usagebar-toggle.sh" "$HOME/.config/herdr/scripts/usagebar-toggle.sh"
migrate_file "$REPO/herdr/scripts/usagebar-sync-fork.sh" "$HOME/.config/herdr/scripts/usagebar-sync-fork.sh"
migrate_file "$REPO/herdr/plugins/usagebar.config.toml" "$HOME/.config/herdr/plugins/config/usagebar/config.toml"

# OMP caps ordinary extension observers at 30s; native compaction needs its API deadline.
if $DRY_RUN; then
  echo "would apply OMP native compaction runtime compatibility patch"
else
  bun "$REPO/omp/native-runtime.ts"
fi

# Repository-owned OMP extensions coexist with Herdr's managed integration.
for extension in accounts profiles herdr native-compaction; do
  link_dir "$REPO/omp/extensions/$extension" "$HOME/.omp/agent/extensions/harness-$extension"
done
migrate_file "$REPO/omp/profiles.ts" "$HOME/.local/bin/omp-profile"
migrate_file "$REPO/herdr/scripts/harness-run.ts" "$HOME/.local/bin/harness-run"
# `~/.config/herdr-cron/jobs.yaml` is deliberately absent. `herdr-cron job add`
# writes it through a temporary file and `os.Rename`, which replaces a symlink
# with a regular file; that already happened once and left the install refusing
# to touch the path. The repo keeps `herdr/cron/jobs.snapshot.yaml` instead.

# Antigravity CLI. `hooks.json` under $AGY_CONFIG belongs to herdr's integration
# installer and `mcp_config.json` to `agy mcp`, so this repo stays out of both
# and owns one plugin directory instead. The remaining two slots are linked to
# the assets that already hold the canonical text: the skill tree shared with
# OMP and Claude Code, and the user's Korean writing instructions.
link_dir "$REPO/agy/config/plugins/harness" "$AGY_CONFIG/plugins/harness"
link_foreign "$HOME/.agents/skills" "$AGY_CONFIG/skills"
link_foreign "$HOME/.claude/CLAUDE.md" "$AGY_CONFIG/rules/AGENTS.md"

if (( ${#conflicts[@]} > 0 )); then
  echo >&2
  echo "error: ${#conflicts[@]} path(s) belong to something this repo will not overwrite:" >&2
  printf '  %s\n' "${conflicts[@]}" >&2
  echo "Everything else was processed. Resolve each ownership conflict and rerun." >&2
  exit 1
fi

if $WITH_CONFIG; then
  if $DRY_RUN; then
    echo "would apply omp settings: $REPO/omp/config.apply.sh"
  else
    "$REPO/omp/config.apply.sh"
  fi
else
  echo "omp settings unchanged (pass --with-config to apply them)"
fi
