#!/usr/bin/env bash
# Rebase the huketo/herdr-agent-usage fork onto upstream and reinstall the plugin.
#
# The fork carries local patches as commits on top of upstream's main, so `gh
# repo sync` (fast-forward only) cannot be used: this script rebases instead and
# force-pushes with --force-with-lease.
#
# `herdr plugin install` is the only update path, and it replaces the managed
# checkout wholesale — so every local change MUST live in a fork commit, never in
# the managed working tree. This script is the whole loop:
#
#   fetch upstream -> rebase patches -> CI-parity checks -> push fork -> reinstall
#
# Usage:
#   usagebar-sync-fork.sh              rebase, check, push, reinstall
#   usagebar-sync-fork.sh --check      stop after the checks (no push, no install)
#   usagebar-sync-fork.sh --no-install rebase, check, push; skip the reinstall
set -euo pipefail

CLONE="${USAGEBAR_FORK_CLONE:-$HOME/huketo/herdr-agent-usage}"
FORK_SLUG="huketo/herdr-agent-usage"
# Every fork-only branch that must follow main. Kept in sync so the upstream PR
# branch never goes stale behind the patches it carries.
PR_BRANCH="fix/codex-spark-submeters"

mode=all
case "${1:-}" in
  --check) mode=check ;;
  --no-install) mode=no-install ;;
  "") ;;
  *) echo "usage: usagebar-sync-fork.sh [--check|--no-install]" >&2; exit 2 ;;
esac

[[ -d "$CLONE/.git" ]] || {
  echo "usagebar-sync-fork: no clone at $CLONE" >&2
  echo "  git clone https://github.com/$FORK_SLUG.git $CLONE" >&2
  exit 1
}
cd "$CLONE"

# A dirty tree would be silently carried through the rebase or lost by it.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "usagebar-sync-fork: $CLONE has uncommitted changes; commit them first:" >&2
  git status --short >&2
  exit 1
fi

git remote get-url upstream >/dev/null 2>&1 ||
  git remote add upstream https://github.com/senna-lang/herdr-agent-usage.git

git fetch upstream --tags --prune
git checkout main
before="$(git rev-parse HEAD)"
base="$(git merge-base HEAD upstream/main)"
patches="$(git rev-list --count "$base"..HEAD)"
echo "usagebar-sync-fork: $patches local patch commit(s) on top of $(git rev-parse --short "$base")"

if ! git rebase upstream/main; then
  echo >&2
  echo "usagebar-sync-fork: rebase stopped on a conflict. Resolve it, then:" >&2
  echo "  cd $CLONE && git add -A && git rebase --continue" >&2
  echo "  # or drop a patch upstream has since adopted: git rebase --skip" >&2
  echo "Re-run this script when the rebase finishes." >&2
  exit 1
fi

after="$(git rev-parse HEAD)"
if [[ "$before" == "$after" ]]; then
  echo "usagebar-sync-fork: already on upstream/main ($(git rev-parse --short HEAD))"
else
  echo "usagebar-sync-fork: rebased $(git rev-parse --short "$before") -> $(git rev-parse --short "$after")"
fi

# The same core checks CI runs (see CONTRIBUTING.md). A rebase can compile and
# still be wrong, so the tests gate the push.
echo "usagebar-sync-fork: gofmt / vet / test"
fmt="$(gofmt -l .)"
[[ -z "$fmt" ]] || { echo "gofmt would rewrite:" >&2; echo "$fmt" >&2; exit 1; }
go vet ./...
go test ./...

[[ "$mode" == check ]] && { echo "usagebar-sync-fork: --check done, nothing pushed"; exit 0; }

git push --force-with-lease origin main
git branch -f "$PR_BRANCH" main
git push --force-with-lease origin "$PR_BRANCH"

[[ "$mode" == no-install ]] && { echo "usagebar-sync-fork: pushed; skipping reinstall"; exit 0; }

# Reinstall rebuilds bin/usagebar from the pushed fork commit via the [[build]]
# hook. Herdr picks the new binary up on the next status/focus event; a limits
# pane that is already open keeps running the old process until reopened.
herdr plugin install "$FORK_SLUG" -y
echo "usagebar-sync-fork: installed $(git rev-parse --short main) — reopen the Agent Usage pane (f9) to pick it up"
