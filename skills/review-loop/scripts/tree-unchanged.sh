#!/usr/bin/env bash
# tree-unchanged.sh snapshot <worktree> > before.txt      (run before delegating the reviewer)
# tree-unchanged.sh check <worktree> <sha> <before.txt>   (run after it returns)
# Read-only proof for a reviewer that ran with write access in a linked worktree. `check` exits 0 only when HEAD is
# still <sha>, the worktree has no staged, unstaged, or untracked change, and the shared git control files that can
# run code or redirect git (config, config.worktree, hooks/, info/) match the snapshot. Ref changes are listed but do
# not fail, because other workers may commit to their own branches meanwhile. Ignored files are counted, not failed.
# Every git call disables hooks and fsmonitor, so a tampered config cannot run code during the check itself.
# This catches a well-meaning reviewer's stray writes; it is not a sandbox against a hostile one (use codex/review.ts).
set -euo pipefail
usage() { echo 'usage: tree-unchanged.sh snapshot <worktree> | check <worktree> <sha> <before.txt>' >&2; exit 2; }
export GIT_CONFIG_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
g() { git -c core.fsmonitor=false -c core.hooksPath=/dev/null -C "$wt" "$@"; }

snapshot() { # resolved git paths, control-file digests (symlinks by target), then refs
  local common f
  common=$(g rev-parse --path-format=absolute --git-common-dir)
  echo "control common-dir $(readlink -f "$common")"
  for f in "$common/config" "$common/config.worktree" "$common"/worktrees/*/config.worktree "$common/hooks" "$common/info"; do
    if [ -L "$f" ]; then
      echo "symlink $(readlink -- "$f")  ${f#"$common"/}"
    elif [ -d "$f" ]; then
      (cd "$f" && find . \( -type f -o -type l \) -print0 | sort -z | while IFS= read -r -d '' e; do
        if [ -L "$e" ]; then echo "symlink $(readlink -- "$e")  ${e#./}"; else sha256sum -- "$e" | sed 's|  \./|  |'; fi
      done) | sed "s|  |  ${f#"$common"/}/|"
    elif [ -f "$f" ]; then
      sha256sum -- "$f" | sed "s|  .*|  ${f#"$common"/}|"
    fi
  done | sed 's/^/control /'
  g for-each-ref --format='ref %(objectname) %(refname)'
}

case ${1:-} in
  snapshot) [ $# -eq 2 ] || usage; wt=$2; snapshot ;;
  check)
    [ $# -eq 4 ] || usage
    wt=$2 before=$4
    [ -f "$before" ] || { echo "missing snapshot: $before" >&2; exit 2; }
    now=$(snapshot)
    control=$(diff <(grep '^control ' "$before") <(printf '%s\n' "$now" | grep '^control ') || true)
    refs=$(diff <(grep '^ref ' "$before") <(printf '%s\n' "$now" | grep '^ref ') | grep '^[<>]' || true)
    head=$(g rev-parse HEAD)
    changes=$(g status --porcelain=v1 --untracked-files=all)
    ignored=$(g status --porcelain=v1 --ignored=matching | grep -c '^!!' || true)
    [ -z "$refs" ] || { echo "NOTE refs moved (judge whether another writer explains them):"; printf '%s\n' "$refs" | head -n 20; }
    if [ -n "$control" ]; then echo "CHANGED git control files"; printf '%s\n' "$control" | head -n 20; exit 1; fi
    want=$(g rev-parse --verify --quiet "$3^{commit}") || { echo "CHANGED $3 is not a commit in this worktree's repository"; exit 1; }
    if [ "$head" != "$want" ]; then echo "CHANGED head $head != $want"; g log --oneline "$want..$head" 2>/dev/null | head -n 20; exit 1; fi
    if [ -n "$changes" ]; then echo "CHANGED working tree"; printf '%s\n' "$changes" | head -n 50; exit 1; fi
    echo "UNCHANGED head ${head:0:12}; ignored entries $ignored"
    ;;
  *) usage ;;
esac
