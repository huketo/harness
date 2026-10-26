#!/usr/bin/env bash
# review-escalate.sh <review-tier.txt> [review.md ...]
# Raises the tier in review-tier.txt (review-tier.sh output) to the highest `TIER: <none|logic|security>` line a
# review states in its header: the lines before its first finding (`S<n> [`). Never lowers it. Prints the first line.
set -euo pipefail
[ $# -ge 1 ] || { echo 'usage: review-escalate.sh <review-tier.txt> [review.md ...]' >&2; exit 2; }
tf=$1
awk '
BEGIN { rank["none"] = 0; rank["logic"] = 1; rank["security"] = 2; rounds["none"] = 0; rounds["logic"] = 3; rounds["security"] = 5 }
FNR == NR { kept[++n] = $0; next }
FNR == 1 { head = 1 }
/^S[0-9]+ \[/ { head = 0 }
head && toupper($1) == "TIER:" && ($2 in rank) && NF == 2 && rank[$2] > rank[best] { best = $2; src = FILENAME }
END {
  if (kept[1] !~ /^tier=(none|logic|security) rounds=[0-9]+ files=[0-9]+$/) { print "review-escalate: not a tier line: " kept[1] > "/dev/stderr"; exit 2 }
  split(kept[1], f, /[= ]/); cur = f[2]
  if (best != "" && rank[best] > rank[cur]) { kept[1] = "tier=" best " rounds=" rounds[best] " files=" f[6]; kept[++n] = best "\t-\tescalated by " src }
  for (i = 1; i <= n; i++) print kept[i]
}' "$@" > "$tf.tmp" || { rm -f "$tf.tmp"; exit 2; }
mv "$tf.tmp" "$tf"
head -n 1 "$tf"
