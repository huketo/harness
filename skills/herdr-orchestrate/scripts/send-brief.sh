#!/usr/bin/env bash
# send-brief.sh <agent> <prompt> [seconds]
# Sends one prompt to a herdr agent. Refuses a prompt whose first non-blank character an agent TUI
# runs as a command (omp, Claude Code, Codex: `!` shell, `/` slash command; omp: `$` Python), then
# exits 0 only once the agent is observed working within <seconds> (default 30).
set -uo pipefail
[ $# -ge 2 ] && [ $# -le 3 ] || { echo 'usage: send-brief.sh <agent> <prompt> [seconds]' >&2; exit 2; }
agent=$1 prompt=$2 secs=${3:-30}
lead=${prompt#"${prompt%%[![:space:]]*}"}
case ${lead:0:1} in
  '!' | '/' | '$') echo "send-brief: refused: a prompt starting with '${lead:0:1}' runs as a command in the agent TUI" >&2; exit 3 ;;
esac
out=$(herdr agent prompt "$agent" "$prompt" --wait --until working --timeout $((secs * 1000)) 2>&1)
rc=$?
status=$(jq -r '.result.agent.agent_status // empty' <<<"$out" 2>/dev/null)
if [ "$rc" -ne 0 ] || [ "$status" != working ]; then
  echo "send-brief: $agent did not reach working within ${secs}s (exit $rc): $out" >&2
  exit 1
fi
echo "send-brief: $agent working"
