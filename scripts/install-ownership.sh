#!/usr/bin/env bash
# Known harness peers share slots; private overrides public, never unrelated entries.
owner_priority() {
  case "$1" in
    huketo.harness-public) printf '10' ;;
    huketo.harness-private) printf '20' ;;
    *) return 1 ;;
  esac
}
IFS= read -r HARNESS_OWNER < "$REPO/.harness-owner"
HARNESS_PRIORITY=$(owner_priority "$HARNESS_OWNER") || {
  echo 'Unknown harness owner' >&2
  exit 1
}
peer_link_policy() {
  PEER_ACTION=foreign
  [[ -L "$2" ]] || return 0
  local source resolved relative directory peer priority
  source=$(readlink -f -- "$1" 2>/dev/null) || return 0
  case "$source" in
    "$REPO"/*) relative=${source#"$REPO"/} ;;
    *) return 0 ;;
  esac
  resolved=$(readlink -f -- "$2" 2>/dev/null) || return 0
  directory=$(dirname "$resolved")
  while [[ "$directory" != / ]]; do
    if [[ -f "$directory/.harness-owner" ]]; then
      IFS= read -r peer < "$directory/.harness-owner"
      priority=$(owner_priority "$peer") || return 0
      [[ "$resolved" = "$directory/$relative" ]] || return 0
      if [[ "$peer" = "$HARNESS_OWNER" ]] || (( HARNESS_PRIORITY > priority )); then
        PEER_ACTION=replace
      else
        PEER_ACTION=keep
      fi
      return 0
    fi
    directory=$(dirname "$directory")
  done
}
