#!/usr/bin/env bash
# Run from any directory; update only the clone that owns this script.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
SKILLS_ONLY=false
WITH_CONFIG=false
for arg in "$@"; do
  case "$arg" in
    --skills-only) SKILLS_ONLY=true ;;
    --with-config) WITH_CONFIG=true ;;
    --help|-h)
      echo "usage: bash update.sh [--skills-only | --with-config]"
      echo "Fast-forward this clean main checkout from origin/main, then reinstall."
      exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
if $SKILLS_ONLY && $WITH_CONFIG; then
  echo "--skills-only cannot be combined with --with-config" >&2
  exit 2
fi
if [[ "$(git -C "$REPO" symbolic-ref --quiet --short HEAD)" != main ]]; then
  echo "update requires main; leave review branches and detached pins unchanged" >&2
  exit 1
fi
if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
  echo "update requires a clean checkout; preserve and resolve local work first" >&2
  exit 1
fi
git -C "$REPO" pull --ff-only origin main
exec bash "$REPO/install.sh" "$@"
