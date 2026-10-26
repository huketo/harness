#!/usr/bin/env bash
# tree-unchanged.test.sh — cases for tree-unchanged.sh. Prints PASS/FAIL per case and exits 1 on any failure.
set -uo pipefail
# Fixture commits must not inherit the workstation's signer or hooks.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid
here=$(dirname "$(readlink -f "$0")")
fail=0
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
repo=$tmp/repo wt=$tmp/child
git init -q "$repo" && git -C "$repo" config user.email t@example.invalid && git -C "$repo" config user.name t
printf 'a\n' > "$repo/a"; printf 'out/\n' > "$repo/.gitignore"; git -C "$repo" add -A; git -C "$repo" commit -qm base
base=$(git -C "$repo" rev-parse HEAD)
git -C "$repo" worktree add -q "$wt" -b child
"$here/tree-unchanged.sh" snapshot "$repo" > "$tmp/before"
result() { # <name> <expected exit> <got exit>
  if [ "$3" = "$2" ]; then echo "PASS $1: exit $3"; else echo "FAIL $1: expected exit $2, got $3"; fail=1; fi
}
expect() { # <name> <expected exit> <setup command> <cleanup command>
  eval "$3"
  "$here/tree-unchanged.sh" check "$wt" "$base" "$tmp/before" > "$tmp/out"; result "$1" "$2" $?
  eval "$4"
}
expect 'clean child worktree' 0 ':' ':'
expect 'ignored build output only' 0 'mkdir -p "$wt/out"; : > "$wt/out/x"' 'rm -rf "$wt/out"'
expect 'unstaged edit' 1 'printf b > "$wt/a"' 'git -C "$wt" checkout -q -- a'
expect 'untracked file' 1 ': > "$wt/new"' 'rm "$wt/new"'
expect 'staged edit' 1 'printf c > "$wt/a"; git -C "$wt" add a' 'git -C "$wt" reset -q --hard "$base"'
expect 'new commit' 1 'git -C "$wt" commit -q --allow-empty -m x' 'git -C "$wt" reset -q --hard "$base"'
expect 'shared config gains fsmonitor' 1 'cp "$repo/.git/config" "$tmp/config.bak"; git -C "$wt" config core.fsmonitor "touch $tmp/pwned"' 'cp "$tmp/config.bak" "$repo/.git/config"'
if [ -e "$tmp/pwned" ]; then echo "FAIL fsmonitor command ran during the check"; fail=1; else echo "PASS fsmonitor command did not run"; fi
expect 'new hook in the common dir' 1 'printf "#!/bin/sh\n" > "$repo/.git/hooks/post-checkout"' 'rm "$repo/.git/hooks/post-checkout"'
expect 'hook added as a symlink' 1 'ln -s /bin/true "$repo/.git/hooks/pre-commit"' 'rm "$repo/.git/hooks/pre-commit"'
expect 'child gitdir gains config.worktree' 1 'printf "[core]\n\tfsmonitor = x\n" > "$repo/.git/worktrees/child/config.worktree"' 'rm "$repo/.git/worktrees/child/config.worktree"'
expect 'child .git redirected to another repository' 1 'cp "$wt/.git" "$tmp/dotgit.bak"; git init -q "$tmp/other"; git -C "$tmp/other" commit -q --allow-empty -m o; printf "gitdir: %s\n" "$tmp/other/.git" > "$wt/.git"' 'cp "$tmp/dotgit.bak" "$wt/.git"'
expect 'another branch moved (noted, not failed)' 0 'git -C "$repo" commit -q --allow-empty -m other' 'git -C "$repo" reset -q --hard "$base"'
grep -q '^NOTE refs moved' "$tmp/out" && echo "PASS ref move is reported" || { echo "FAIL ref move is reported"; fail=1; }
"$here/tree-unchanged.sh" check "$wt" "$base" > /dev/null 2>&1; result 'missing snapshot argument' 2 $?
"$here/tree-unchanged.sh" check "$wt" "$base" "$tmp/nope" > /dev/null 2>&1; result 'missing snapshot file' 2 $?
exit $fail
