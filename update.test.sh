#!/usr/bin/env bash
# Temporary-local integration tests. No network or real HOME changes.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=test@example.invalid
mkdir -p "$HOME"
git init -q --bare --initial-branch=main "$TMP/origin.git"
git clone -q "$TMP/origin.git" "$TMP/author"
cp "$SOURCE/install.sh" "$TMP/author/install.sh"
cp "$SOURCE/update.sh" "$TMP/author/update.sh"
mkdir -p "$TMP/author/skills/example"
printf '%s\n' '---' 'name: example' '---' > "$TMP/author/skills/example/SKILL.md"
git -C "$TMP/author" add .
git -C "$TMP/author" commit -qm initial
git -C "$TMP/author" push -q origin main
git clone -q "$TMP/origin.git" "$TMP/installed"
# Skills-only works without personal instructions and leaves config untouched.
mkdir -p "$HOME/.codex/rules"
printf 'keep\n' > "$HOME/.codex/rules/default.rules"
bash "$TMP/installed/install.sh" --skills-only
[[ -L "$HOME/.agents/skills/example" && -L "$HOME/.claude/skills/example" ]]
[[ "$(cat "$HOME/.codex/rules/default.rules")" == keep ]]
[[ ! -e "$HOME/.codex/rules/harness.rules" && ! -e "$HOME/.gemini" ]]
# Fast-forward + reinstall discovers a newly added skill.
mkdir -p "$TMP/author/skills/added"
printf '%s\n' '---' 'name: added' '---' > "$TMP/author/skills/added/SKILL.md"
git -C "$TMP/author" add .
git -C "$TMP/author" commit -qm add-skill
git -C "$TMP/author" push -q origin main
# Fetch preview must neither advance HEAD nor install the incoming skill.
before="$(git -C "$TMP/installed" rev-parse HEAD)"
preview="$(bash "$TMP/installed/update.sh" --skills-only --dry-run)"
[[ "$preview" == *add-skill* ]]
[[ "$(git -C "$TMP/installed" rev-parse HEAD)" == "$before" ]]
[[ ! -e "$HOME/.agents/skills/added" ]]
# A user's rebase preference must not change the fast-forward-only mechanism.
git -C "$TMP/installed" config pull.rebase true
bash "$TMP/installed/update.sh" --skills-only
[[ -L "$HOME/.agents/skills/added" && -L "$HOME/.claude/skills/added" ]]
[[ "$(git -C "$TMP/installed" rev-parse HEAD)" == "$(git -C "$TMP/author" rev-parse HEAD)" ]]
# A foreign skill is preserved and reported, not overwritten.
rm "$HOME/.claude/skills/added" "$HOME/.agents/skills/added"
mkdir "$HOME/.agents/skills/added"
if bash "$TMP/installed/install.sh" --skills-only; then exit 1; fi
[[ -d "$HOME/.agents/skills/added" && ! -L "$HOME/.agents/skills/added" ]]
[[ ! -e "$HOME/.claude/skills/added" && ! -L "$HOME/.claude/skills/added" ]]
# Unknown or retired options, dirty work and topic branches never update the checkout.
if bash "$TMP/installed/update.sh" --skills-only --with-config; then exit 1; fi
printf 'dirty\n' > "$TMP/installed/untracked"
if bash "$TMP/installed/update.sh" --skills-only; then exit 1; fi
rm "$TMP/installed/untracked"
git -C "$TMP/installed" switch -qc topic
if bash "$TMP/installed/update.sh" --skills-only; then exit 1; fi
git -C "$TMP/installed" switch -q main
# A divergent main is not merged or reset.
printf 'local\n' > "$TMP/installed/local"
git -C "$TMP/installed" add local
git -C "$TMP/installed" commit -qm local
printf 'remote\n' > "$TMP/author/remote"
git -C "$TMP/author" add remote
git -C "$TMP/author" commit -qm remote
git -C "$TMP/author" push -q origin main
before="$(git -C "$TMP/installed" rev-parse HEAD)"
if bash "$TMP/installed/update.sh" --skills-only; then exit 1; fi
[[ "$(git -C "$TMP/installed" rev-parse HEAD)" == "$before" ]]
printf 'PASS: skills-only ownership, fast-forward reinstall, and update refusal cases\n'
