#!/usr/bin/env bash
# review-tier.sh <repo> <base> [head]
# Classifies the change merge-base(base, head)..head by review-tiers.tsv and prints
# `tier=<none|logic|security> rounds=<0|1|3> files=<n>`, then `<tier>\t<file>\t<rule>` per changed file.
set -euo pipefail
[ $# -ge 2 ] && [ $# -le 3 ] || { echo 'usage: review-tier.sh <repo> <base> [head]' >&2; exit 2; }
repo=$1 base=$2 head=${3:-HEAD}
rules=$(dirname "$(readlink -f "$0")")/review-tiers.tsv
mb=$(git -C "$repo" merge-base "$base" "$head")
awk '
function applies(i, f, p,   c, k) {
  if (kind[i] == "path") return p ~ re[i]
  if (kind[i] == "content") {
    for (c = 1; c <= cnt[f]; c++) if (line[f, c] ~ re[i]) return 1
    for (c = 1; c <= hc[f]; c++) if (ctx[f, c] ~ re[i]) return 1
    return 0
  }
  for (c = 1; c <= cnt[f]; c++) if (line[f, c] !~ /^[[:space:]]*$/) { if (line[f, c] !~ re[i]) return 0; k++ }
  return k > 0
}
BEGIN { rank["none"] = 0; rank["logic"] = 1; rank["security"] = 2; rounds["none"] = 0; rounds["logic"] = 1; rounds["security"] = 3 }
FNR == NR {
  if (/^#/ || !NF) next
  split($0, r, "\t")
  if (!(r[1] in rank) || r[2] !~ /^(path|content|lines)$/ || r[3] == "") { print "review-tier: bad rule: " $0 > "/dev/stderr"; failed = 1; exit 2 }
  tier[++n] = r[1]; kind[n] = r[2]; re[n] = tolower(r[3]); next
}
/^diff --git / { file[++nf] = $0; sub(/^diff --git a\/.* b\//, "", file[nf]); hdr = 1; next }
# A hunk header carries the enclosing line git found (e.g. `allowed_user_ids = [` above a changed element).
/^@@/ { hdr = 0; s = $0; sub(/^@@[^@]*@@ ?/, "", s); if (s != "") ctx[nf, ++hc[nf]] = tolower(s); next }
!hdr && /^[-+]/ { line[nf, ++cnt[nf]] = tolower(substr($0, 2)) }
END {
  if (failed) exit 2
  top = "none"
  for (f = 1; f <= nf; f++) {
    t = "logic"; why = "default"; p = tolower(file[f]); hit = 0
    # Security rules from either file win before any other rule, so a repository rule never shadows one.
    for (i = 1; i <= n && !hit; i++) if (tier[i] == "security" && applies(i, f, p)) { t = tier[i]; why = kind[i] " " re[i]; hit = 1 }
    for (i = 1; i <= n && !hit; i++) if (applies(i, f, p)) { t = tier[i]; why = kind[i] " " re[i]; hit = 1 }
    if (rank[t] > rank[top]) top = t
    out = out t "\t" file[f] "\t" why "\n"
  }
  printf "tier=%s rounds=%d files=%d\n%s", top, rounds[top], nf, out
}' <({ git -C "$repo" show "$mb:.review-tiers.tsv" 2>/dev/null || true; cat "$rules"; }) \
   <(git -C "$repo" diff --no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ -U0 "$mb" "$head")
