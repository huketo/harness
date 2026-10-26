#!/usr/bin/env bash
# review-tier.test.sh — synthetic regression cases for classification and escalation.
# Prints PASS/FAIL per case and exits 1 on any failure; uses temporary local repositories only.
set -euo pipefail
# Fixture commits must not inherit the workstation's signer or hooks.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here=$(dirname "$(readlink -f "$0")")
fail=0
check() { # <name> <expected tier> <repo> <base> <head>
  local got
  got=$("$here/review-tier.sh" "$3" "$4" "$5" | head -n 1); got=${got%% *}; got=${got#tier=}
  if [ "$got" = "$2" ]; then echo "PASS $1: $got"; else echo "FAIL $1: expected $2, got ${got:-error}"; fail=1; fi
}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git -C "$tmp" init -q && git -C "$tmp" config user.email t@example.invalid && git -C "$tmp" config user.name t
change() { # <name> <expected tier> <file> <before> <after>: commits <before>, then <after>, and checks that one change
  mkdir -p "$tmp/$(dirname "$3")"
  printf '%b' "$4" > "$tmp/$3"; git -C "$tmp" add -A; git -C "$tmp" commit -qm base
  printf '%b' "$5" > "$tmp/$3"; git -C "$tmp" commit -qam head
  check "$1" "$2" "$tmp" HEAD^ HEAD
}

# r1 blocking 1: agent-instruction documents are not docs, and security wording in them is security.
change 'instruction doc weakens a permission rule' security docs/agents/authority.md \
  'Do not add permission-bypass flags as an installation default.\n' 'Add permission-bypass flags as an installation default.\n'
change 'SKILL.md behavior change' logic skills/x/SKILL.md 'Run the tests.\n' 'Skip the tests.\n'
change 'skill reference behavior change' logic skills/x/references/launch.md 'Wait for the agent.\n' 'Do not wait.\n'
change 'ROLE.md behavior change' logic agents/dev/ROLE.md 'Quote arguments.\n' 'Pass arguments as typed.\n'
# r1 blocking 2: a value change in an approval setting is security.
change 'allowed_user_ids value' security herdr/hitl.config.example.toml \
  '[telegram]\nallowed_user_ids = ["1"]\n' '[telegram]\nallowed_user_ids = ["2"]\n'
change 'allowed_user_ids element on its own line' security herdr/hitl.toml \
  'allowed_user_ids = [\n  "1",\n]\n' 'allowed_user_ids = [\n  "2",\n]\n'
# r1 blocking 3: no config change is none just because keys look preserved.
change 'json key renamed on one line' logic config.json '{"mode":"safe"}\n' '{"execute":"safe"}\n'
change 'toml section renamed' logic config.toml '[a]\nx = 1\n' '[b]\nx = 1\n'
change 'plain config value' logic config.json '{"timeout": 30}\n' '{"timeout": 60}\n'
# none remains for plain docs and comment-only edits.
change 'plain docs' none docs/guide.md 'Old wording.\n' 'New wording.\n'
change 'comment-only code edit' none lib/run.sh 'echo hi\n# old note\n' 'echo hi\n# new note\n'
# A repository's own rules extend the harness rules but never shadow a harness security rule.
printf 'logic\tpath\t^docs/agents/\n' > "$tmp/.review-tiers.tsv"
change 'repo logic rule over an approval change' security docs/agents/merge.md \
  'Merge after the approver approves.\n' 'Merge without waiting for the approver.\n'
change 'repo logic rule over a plain agent doc' logic docs/agents/style.md 'Short sentences.\n' 'Plain words.\n'
rm "$tmp/.review-tiers.tsv"; git -C "$tmp" commit -qam 'drop repo rules'

# r2 blocking: no keyword list names every boundary, so the classifier is a floor and a reviewer escalates.
change 'restrictToolNames true->false (classifier floor)' logic omp/review.ts \
  'function buildRestrictedReviewSessionOptions() {\n  return { restrictToolNames: true };\n}\n' \
  'function buildRestrictedReviewSessionOptions() {\n  return { restrictToolNames: false };\n}\n'
esc=$(mktemp -d); trap 'rm -rf "$tmp" "$esc"' EXIT
"$here/review-tier.sh" "$tmp" HEAD^ HEAD > "$esc/review-tier.txt"
escalated() { # <name> <expected tier> <review text>: feeds one review to review-escalate.sh against the tier above
  local got
  printf '%b' "$3" > "$esc/review-r1.md"
  got=$("$here/review-escalate.sh" "$esc/review-tier.txt" "$esc/review-r1.md"); got=${got%% *}; got=${got#tier=}
  if [ "$got" = "$2" ]; then echo "PASS $1: $got"; else echo "FAIL $1: expected $2, got ${got:-error}"; fail=1; fi
}
verdict='VERDICT: CHANGES\n'
escalated 'tier line after the first finding is ignored' logic "${verdict}S1 [blocker] omp/review.ts:2 claim. Fix: x\nTIER: security\n"
escalated 'an unknown tier word is ignored' logic "${verdict}TIER: critical\n"
escalated 'restrictToolNames: logic (escalated by review)' security "${verdict}TIER: security\nS1 [blocker] omp/review.ts:2 claim. Fix: x\n"
escalated 'a later review stating none does not lower it' security "${verdict}TIER: none\n"

exit $fail
