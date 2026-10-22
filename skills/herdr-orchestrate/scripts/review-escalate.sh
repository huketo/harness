#!/usr/bin/env bash
# review-escalate.sh <review-tier.txt> [review.md ...]
# Raises the tier in review-tier.txt (review-tier.sh output) to the highest `tier: <none|logic|security>` line a
# review states in its verdict header (the `# 판정` section). Never lowers it. Prints the resulting first line.
set -euo pipefail
[ $# -ge 1 ] || { echo 'usage: review-escalate.sh <review-tier.txt> [review.md ...]' >&2; exit 2; }
tf=$1
awk '
BEGIN { rank["none"] = 0; rank["logic"] = 1; rank["security"] = 2; rounds["none"] = 0; rounds["logic"] = 1; rounds["security"] = 3 }
FNR == NR { kept[++n] = $0; next }
FNR == 1 { head = 0 }
/^# 판정/ { head = 1; next }
/^# / { head = 0; next }
head && /^tier: (none|logic|security)[[:space:]]*$/ && rank[$2] > rank[best] { best = $2; src = FILENAME }
END {
  if (kept[1] !~ /^tier=(none|logic|security) rounds=[0-9]+ files=[0-9]+$/) { print "review-escalate: not a tier line: " kept[1] > "/dev/stderr"; exit 2 }
  split(kept[1], f, /[= ]/); cur = f[2]
  if (best != "" && rank[best] > rank[cur]) { kept[1] = "tier=" best " rounds=" rounds[best] " files=" f[6]; kept[++n] = best "\t-\tescalated by " src }
  for (i = 1; i <= n; i++) print kept[i]
}' "$@" > "$tf.tmp" || { rm -f "$tf.tmp"; exit 2; }
mv "$tf.tmp" "$tf"
head -n 1 "$tf"
