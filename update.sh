#!/usr/bin/env bash
# Run from any directory; update only the clone that owns this script.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
SKILLS_ONLY=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --skills-only) SKILLS_ONLY=true ;;
    --dry-run) DRY_RUN=true ;;
    --help|-h)
      echo "usage: bash update.sh [--dry-run] [--skills-only]"
      echo "Fetch and show incoming commits, then fast-forward and reinstall unless --dry-run."
      exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
if [[ "$(git -C "$REPO" symbolic-ref --quiet --short HEAD)" != main ]]; then
  echo "update requires main; leave review branches and detached pins unchanged" >&2
  exit 1
fi
if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
  echo "update requires a clean checkout; preserve and resolve local work first" >&2
  exit 1
fi
git -C "$REPO" fetch origin main
git -C "$REPO" log --oneline HEAD..origin/main
if $DRY_RUN; then
  echo "dry-run: checkout and installed assets unchanged; fetched refs only"
  exit 0
fi
git -C "$REPO" merge --ff-only FETCH_HEAD
exec bash "$REPO/install.sh" "$@"
