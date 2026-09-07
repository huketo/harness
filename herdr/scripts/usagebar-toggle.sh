#!/usr/bin/env bash
# Toggle the Agent Usage (usagebar) limits pane as a right-hand split.
#
# Open  -> split right in the focused workspace, unfocused, resized to WIDTH.
# Open again while one exists anywhere -> close it. Single instance by design.
#
# herdr cannot set a split size at creation (`herdr plugin pane open` has no
# --width; the socket API's width/height apply to popup placement only), so the
# pane always starts at ratio 0.5 and is converged onto WIDTH columns with
# `herdr pane resize`, whose --amount is a delta on the split ratio.
set -euo pipefail

# A `type = "shell"` keybinding runs detached, so PATH is not guaranteed to
# carry the install dir.
HERDR="${HERDR_BIN_PATH:-}"
if [[ -z "$HERDR" ]]; then
  HERDR="$(command -v herdr || true)"
fi
if [[ -z "$HERDR" ]]; then
  HERDR="$HOME/.local/bin/herdr"
fi
# herdr-plugin.toml names the pane "Agent Usage"; PaneInfo carries no plugin id,
# so the label is the only in-band detector.
LABEL="Agent Usage"
# 54+ columns keeps full-width bars and the "resets in" hints; below 32 the
# panel collapses to one line per provider.
WIDTH="${USAGEBAR_PANE_WIDTH:-64}"

existing="$("$HERDR" pane list |
  jq -r --arg l "$LABEL" '[.result.panes[] | select(.label == $l) | .pane_id][0] // ""')"

if [[ -n "$existing" ]]; then
  "$HERDR" plugin pane close "$existing" >/dev/null
  exit 0
fi

pane="$("$HERDR" plugin pane open \
  --plugin usagebar \
  --entrypoint limits \
  --placement split \
  --direction right \
  --no-focus |
  jq -r '.result.plugin_pane.pane.pane_id // ""')"

[[ -n "$pane" ]] || exit 1

for _ in 1 2 3 4 5 6; do
  read -r current area < <("$HERDR" pane layout --pane "$pane" |
    jq -r --arg p "$pane" '.result.layout
      | [(.panes[] | select(.pane_id == $p) | .rect.width), .area.width]
      | @tsv')
  [[ -n "${current:-}" && -n "${area:-}" && "$area" -gt 0 ]] || break

  delta=$((current - WIDTH))
  [[ "${delta#-}" -le 1 ]] && break

  direction=right
  [[ "$delta" -lt 0 ]] && direction=left
  amount="$(awk -v d="$delta" -v a="$area" 'BEGIN { printf "%.6f", (d < 0 ? -d : d) / a }')"

  "$HERDR" pane resize --pane "$pane" --direction "$direction" --amount "$amount" >/dev/null
done
