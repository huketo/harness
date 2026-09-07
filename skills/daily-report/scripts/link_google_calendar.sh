#!/usr/bin/env bash
# One-time Google Calendar linking for the daily-report skill.
#
# The calendar half of the daily report reads Google Calendar's "secret address
# in iCal format": one HTTPS GET returns the whole calendar as a single .ics.
# No OAuth client, no Google Cloud project, no token to refresh. The URL itself
# is the credential, so it is stored in a mode-600 config file and never
# printed, never passed on a command line, never committed.
#
# What the human does, per calendar, in the browser:
#   1. Google Calendar -> settings (gear) -> "Settings for my calendars"
#   2. Pick the calendar -> "Integrate calendar"
#   3. Copy "Secret address in iCal format"
#      (https://calendar.google.com/calendar/ical/<id>/private-<token>/basic.ics)
#   4. Run this script and paste it. The paste is not echoed.
#
# A secret address can be reset in the same panel ("Reset" next to it), which
# invalidates the old URL. Re-run this script with the same label to replace it.
#
# Usage:
#   link_google_calendar.sh          add or replace a calendar, fetch, verify
#   link_google_calendar.sh --check  report state only, change nothing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${DAILY_REPORT_CALENDARS:-$HOME/.config/daily-report/calendars.conf}"
KHAL_CONFIG_FILE="${KHAL_CONFIG:-$HOME/.config/khal/config}"
VDIR="$HOME/.local/share/calendars"
CHECK_ONLY=false

case "${1:-}" in
  --check) CHECK_ONLY=true ;;
  --help|-h) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "unknown argument: $1" >&2; exit 2 ;;
esac

die() { echo "error: $*" >&2; exit 1; }

command -v khal >/dev/null 2>&1 || die "khal is not on PATH. Install with: uv tool install --python 3.13 khal"
command -v python3 >/dev/null 2>&1 || die "python3 is not on PATH"

report_state() {
  echo "calendar list : $CONFIG_FILE"
  if [[ -f "$CONFIG_FILE" ]]; then
    local label count
    while read -r label; do
      count=$(find "$VDIR/$label" -maxdepth 1 -name '*.ics' 2>/dev/null | wc -l | tr -d ' ')
      printf '  %-16s %s mirrored events\n' "$label" "$count"
    done < <(sed -n 's/^\([A-Za-z0-9][A-Za-z0-9._-]*\)[[:space:]]*=.*/\1/p' "$CONFIG_FILE")
  else
    echo "  (absent: no calendar linked on this machine yet)"
  fi
  echo "khal config   : $KHAL_CONFIG_FILE"
  echo "mirror        : $VDIR"
}

write_khal_config() {
  if [[ -f "$KHAL_CONFIG_FILE" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$KHAL_CONFIG_FILE")"
  cat > "$KHAL_CONFIG_FILE" <<'CFG'
# Written by daily-report/scripts/link_google_calendar.sh.
# Every mirrored calendar is one directory under the path below; the collector
# writes them, so khal only ever reads.
[calendars]
[[gcal]]
path = ~/.local/share/calendars/*
type = discover
readonly = True

# ISO everywhere: the collector parses khal's output.
[locale]
local_timezone = Asia/Seoul
default_timezone = Asia/Seoul
timeformat = %H:%M
dateformat = %Y-%m-%d
longdateformat = %Y-%m-%d
datetimeformat = %Y-%m-%dT%H:%M
longdatetimeformat = %Y-%m-%dT%H:%M
unicode_symbols = False

[default]
highlight_event_days = False
CFG
  echo "wrote $KHAL_CONFIG_FILE"
}

if $CHECK_ONLY; then
  report_state
  exit 0
fi

report_state
echo

read -r -p "Label for this calendar (e.g. work, personal): " LABEL
[[ "$LABEL" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "label must match [A-Za-z0-9][A-Za-z0-9._-]*"
if [[ "$LABEL" == "gcal" ]]; then
  die "'gcal' is the khal config section name; pick another label"
fi
echo "The label appears as the \`calendar\` field of every event it holds, and"
echo "the skill only drafts work calendars into a report. Name it accordingly."
echo

echo "Paste the secret iCal address (not echoed):"
read -r -s SECRET_URL
echo
[[ -n "$SECRET_URL" ]] || die "no URL given"
if [[ ! "$SECRET_URL" =~ ^https://calendar\.google\.com/calendar/ical/.+/(private-[^/]+|public)/(basic|full)\.ics$ ]]; then
  die "that does not look like a Google iCal address. Expected
  https://calendar.google.com/calendar/ical/<calendar-id>/private-<token>/basic.ics
  Copy it from Google Calendar -> settings -> the calendar -> Integrate calendar."
fi

echo "== probing the feed =="
# The probe imports the collector, so keep its bytecode out of the skill tree.
SECRET_URL="$SECRET_URL" SCRIPT_DIR="$SCRIPT_DIR" PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import os
import sys

sys.path.insert(0, os.environ["SCRIPT_DIR"])
from collect_calendar import fetch, split_feed

try:
    text = fetch(os.environ["SECRET_URL"])
except RuntimeError as exc:
    raise SystemExit(f"error: {exc}")

feed = split_feed(text, None)
name = next(
    (line.split(":", 1)[1] for line in text.splitlines() if line.startswith("X-WR-CALNAME:")),
    "(no X-WR-CALNAME)",
)
print(f"  calendar     : {name}")
print(f"  events       : {feed.count} components -> {len(feed.items)} items")
print(f"  generated at : {feed.generated_at} (Google stamps every DTSTAMP at generation)")
print(f"  attendance   : {'ATTENDEE present' if 'ATTENDEE' in text else 'no ATTENDEE lines: declined events cannot be filtered'}")
PY

mkdir -p "$(dirname "$CONFIG_FILE")"
chmod 700 "$(dirname "$CONFIG_FILE")"
SECRET_URL="$SECRET_URL" LABEL="$LABEL" CONFIG="$CONFIG_FILE" python3 - <<'PY'
import os
import pathlib

path = pathlib.Path(os.environ["CONFIG"])
label = os.environ["LABEL"]
line = f"{label} = {os.environ['SECRET_URL']}"

header = [
    "# daily-report: Google Calendar secret iCal addresses, one per line.",
    "# Each URL is a credential. Mode 600, never committed, never pasted in chat.",
    "#   <label> = https://calendar.google.com/calendar/ical/<id>/private-<token>/basic.ics",
]
lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else list(header)

replaced = False
for index, existing in enumerate(lines):
    stripped = existing.strip()
    if stripped.startswith("#") or "=" not in stripped:
        continue
    if stripped.split("=", 1)[0].strip() == label:
        lines[index] = line
        replaced = True
        break
if not replaced:
    lines.append(line)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
path.chmod(0o600)
print(f"{'replaced' if replaced else 'added'} `{label}` in {path} (mode 600)")
PY
unset SECRET_URL

write_khal_config

echo
echo "== fetching =="
SUMMARY_JSON="$(mktemp)"
trap 'rm -f "$SUMMARY_JSON"' EXIT
python3 "$SCRIPT_DIR/collect_calendar.py" --calendar "$LABEL" > "$SUMMARY_JSON"
SUMMARY_JSON="$SUMMARY_JSON" python3 - <<'PY'
import json
import os

with open(os.environ["SUMMARY_JSON"], encoding="utf-8") as handle:
    data = json.load(handle)
for source in data["sync"]["sources"]:
    print(f"  {source['label']}: " + (
        f"{source['items']} items, {source['written']} written, {source['deleted']} removed"
        if source["ok"] else f"FAILED: {source['error']}"
    ))
print(f"  today: {len(data['events'])} events, dropped {data['dropped']}")
PY

echo
echo "== khal printcalendars =="
khal printcalendars

echo
echo "== khal list today =="
khal list today today

echo
report_state
echo "Done. collect_calendar.py refetches every listed feed on its own from now on."
