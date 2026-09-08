#!/usr/bin/env bash
set -euo pipefail

# Declaratively applies the user-managed OMP settings captured in this repo.
# Record-valued keys (modelRoles, task.agentModelOverrides, and
# retry.fallbackChains) must be passed as whole JSON objects: omp rejects dotted
# paths inside those records.
#
# Purpose/model/effort policy is owned by profiles.json plus user overrides.
# Built-in roles remain compatibility slots, not the user's profile catalogue.

MODE=apply
case "${1:-}" in
  --check) MODE=check ;;
  --help|-h)
    echo "usage: $0 [--check]"
    echo "  --check  report managed values that differ; exit 1 when any differ"
    exit 0
    ;;
  "") ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

command -v omp >/dev/null 2>&1 || { echo "error: omp is not on PATH" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "error: python3 is not on PATH" >&2; exit 2; }
command -v bun >/dev/null 2>&1 || { echo "error: bun is not on PATH" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")" && pwd)"
# Recoverable shake requires the matching runtime patch before any settings write.
if [[ "$MODE" == apply ]]; then
  bun "$ROOT/native-runtime.ts" --check
fi

# Each desired value is canonical JSON. Strings are unquoted before `config set`;
# arrays, objects, booleans, and numbers are passed as JSON.
readarray -t SETTINGS <<'EOF'
modelRoles|{}
symbolPreset|"unicode"
theme.dark|"titanium"
setupVersion|2
dev.autoqaConsent|"granted"
codexResets.autoRedeem|"no"
composer.shape|"box"
statusLine.transparent|false
statusLine.compactThinkingLevel|false
statusLine.preset|"full"
compaction.keepRecentTokens|40000
compaction.methodOrder|["shake","remote","handoff","soft"]
compaction.handoffSaveToDisk|true
compaction.thresholdTokens|-1
compaction.thresholdPercent|75
tools.xdevDocs|"catalog"
tools.intentTracing|false
startup.checkUpdate|true
marketplace.autoUpdate|"notify"
recap.enabled|false
spelling.typoDetection|false
spelling.autocomplete|false
power.sleepPrevention|"off"
skills.enableCodexUser|false
skills.enableClaudeUser|false
skills.enableClaudeProject|false
skills.enablePiUser|false
skills.enablePiProject|false
skills.enableAgentsProject|false
skills.enableAgentsUser|true
task.agentModelOverrides|{"librarian":"@smol","reviewer":"@slow","scout":"@smol","security-reviewer":"@slow","sonic":"@smol","task":"@mid"}
retry.fallbackChains|{}
retry.maxDelayMs|0
retry.usageAwareFallback|true
retry.usageReservePct|10
retry.usageReservePolicy|"auto"
cycleOrder|["smol","mid","default","slow"]
providers.cacheRetention|"auto"
EOF

roles="$(bun "$ROOT/profiles.ts" roles | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), separators=(",", ":")))')"
sol="$(bun "$ROOT/profiles.ts" selector code --defaults)"
opus="$(bun "$ROOT/profiles.ts" selector opus-code --defaults)"
fallbacks="$(python3 - "$sol" "$opus" <<'PY'
import json, sys
sol, opus = sys.argv[1:]
print(json.dumps({
    "anthropic/*": [sol], "mid": [opus], "slow": [opus],
    "smol": [sol, opus], "tiny": [sol, opus],
}, separators=(",", ":")))
PY
)"
for i in "${!SETTINGS[@]}"; do
  case "${SETTINGS[$i]}" in
    modelRoles\|*) SETTINGS[$i]="modelRoles|$roles" ;;
    retry.fallbackChains\|*) SETTINGS[$i]="retry.fallbackChains|$fallbacks" ;;
  esac
done

canonical_value() {
  python3 -c 'import json, sys; data=json.load(sys.stdin); print(json.dumps(data.get("value"), ensure_ascii=False, sort_keys=True, separators=(",", ":")))'
}

config_argument() {
  python3 -c 'import json, sys; value=json.load(sys.stdin); print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))'
}

# `modelRoles.default` is session-owned: OMP writes the running session's
# selector back into it whenever a session resolves or switches its model, so
# the value above is only a bootstrap default for a machine that has none.
# Adopting the live value keeps `--check` from reporting a session's model as
# drift and keeps `apply` from yanking the model out from under a live session.
adopt_session_owned() {
  python3 - "$1" "$2" "$3" <<'PY'
import json
import sys

SESSION_OWNED = {"modelRoles": ("default",)}

key, current_raw, desired_raw = sys.argv[1:4]
current = json.loads(current_raw)
desired = json.loads(desired_raw)
if isinstance(current, dict) and isinstance(desired, dict):
    for subkey in SESSION_OWNED.get(key, ()):
        if subkey in current:
            desired[subkey] = current[subkey]
print(json.dumps(desired, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
PY
}

differences=0
applied=0
total=0

for setting in "${SETTINGS[@]}"; do
  IFS='|' read -r key desired <<<"$setting"
  total=$((total + 1))

  if ! raw="$(omp config get "$key" --json)"; then
    echo "error: failed to read omp setting $key" >&2
    exit 2
  fi
  if ! current="$(printf '%s' "$raw" | canonical_value)"; then
    echo "error: invalid JSON returned for omp setting $key" >&2
    exit 2
  fi

  if ! desired="$(adopt_session_owned "$key" "$current" "$desired")"; then
    echo "error: failed to resolve session-owned subkeys of $key" >&2
    exit 2
  fi

  if [[ "$current" == "$desired" ]]; then
    continue
  fi

  differences=$((differences + 1))
  if [[ "$MODE" == check ]]; then
    printf 'different: %s\n  current: %s\n  desired: %s\n' "$key" "$current" "$desired"
    continue
  fi

  value="$(printf '%s' "$desired" | config_argument)"
  omp config set "$key" -- "$value" >/dev/null
  applied=$((applied + 1))
  echo "applied: $key"
done

if [[ "$MODE" == check ]]; then
  if (( differences > 0 )); then
    echo "omp config: $differences of $total managed settings differ" >&2
    exit 1
  fi
  echo "omp config: all $total managed settings match"
  exit 0
fi

if (( applied == 0 )); then
  echo "omp config: all $total managed settings already match; nothing changed"
else
  echo "omp config: applied $applied setting(s)"
fi
