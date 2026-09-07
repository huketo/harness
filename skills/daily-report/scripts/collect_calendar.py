#!/usr/bin/env python3
"""Collect one KST day of calendar events for the daily report.

The source is Google Calendar's "secret address in iCal format": one HTTPS GET
returns a whole calendar as a single .ics, with no OAuth client, no Google
Cloud project and no token to refresh. The URL itself is the credential, so
every calendar lives in a mode-600 config file, one `label = url` per line
(default `~/.config/daily-report/calendars.conf`).

A feed is a single VCALENDAR holding every event, which khal refuses to read
("contains multiple UIDs"). So each feed is split into a vdir under
`~/.local/share/calendars/<label>/` -- one file per UID, Google's own UID kept,
every VTIMEZONE inlined -- and `khal` is asked for one day, because recurrence
expansion and time zones are the only hard part and khal already does both.

Files are rewritten only when their content changed, so khal's index stays warm
and a failed fetch changes nothing: the mirror on disk is still the truth of the
last successful fetch, so the day is reported with `sync.ok = false` and the
caller decides whether to trust it.

Output: one JSON object on stdout. Diagnostics go to stderr. The secret URLs
never appear in either.

    {
      "date": "2026-09-04",
      "sync": {"ok": true, "skipped": false, "error": null, "sources": [...]},
      "calendars": ["work"],
      "events": [{"start": "2026-09-04T14:00", "kind": "meeting", ...}],
      "dropped": {"cancelled": 1, "declined": 0}
    }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

DEFAULT_CONFIG = Path.home() / ".config/daily-report/calendars.conf"
DEFAULT_VDIR = Path.home() / ".local/share/calendars"
FETCH_TIMEOUT = 30
USER_AGENT = "daily-report-calendar/1"

LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SOURCE_RE = re.compile(r"^(?P<label>[^=]+?)\s*=\s*(?P<url>\S+)$")

# khal --json fields. `cancelled` duplicates `status` but is set even when the
# VEVENT carries no STATUS, so keep both.
JSON_FIELDS = [
    "start",
    "end",
    "start-date",
    "end-date",
    "title",
    "location",
    "description",
    "calendar",
    "categories",
    "all-day",
    "status",
    "cancelled",
    "repeat-pattern",
    "organizer",
    "uid",
]

TRIP_WORDS = ("출장", "외근", "방문", "workshop", "워크샵", "세미나", "컨퍼런스", "conference")
MEETING_WORDS = ("회의", "미팅", "meeting", "정기", "스크럼", "standup", "스탠드업", "리뷰", "review", "1:1", "면담", "킥오프", "kickoff")
LEAVE_WORDS = ("휴가", "연차", "반차", "off", "pto")

# A Google calendar id that is an address is the owner's address; the generated
# ids of secondary and holiday calendars are not.
GENERATED_ID_HOSTS = (
    "group.calendar.google.com",
    "group.v.calendar.google.com",
    "import.calendar.google.com",
)


def kst_today() -> str:
    return datetime.now(KST).date().isoformat()


def read_sources(path: Path) -> list[tuple[str, str]]:
    """Parse `label = url` lines. Raises SystemExit on an unusable config."""
    if not path.is_file():
        raise FileNotFoundError(path)
    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = SOURCE_RE.match(line)
        if not match:
            raise SystemExit(f"{path}:{lineno}: expected `label = url`")
        label = match.group("label").strip()
        if not LABEL_RE.match(label):
            raise SystemExit(f"{path}:{lineno}: bad label {label!r}")
        if label in seen:
            raise SystemExit(f"{path}:{lineno}: duplicate label {label!r}")
        seen.add(label)
        sources.append((label, match.group("url")))
    return sources


def calendar_id(url: str) -> str:
    """The calendar id embedded in a Google iCal URL, percent-decoding included.

    `https://calendar.google.com/calendar/ical/<id>/private-<token>/basic.ics`
    """
    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "calendar" and parts[1] == "ical":
        return urllib.parse.unquote(parts[2])
    return ""


def own_address(sources: list[tuple[str, str]]) -> str | None:
    for _, url in sources:
        ident = calendar_id(url)
        if "@" in ident and not ident.endswith(GENERATED_ID_HOSTS):
            return ident
    return None


def fetch(url: str) -> str:
    """GET one feed. The URL is a credential: keep it out of every message."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/calendar"}
    )
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        hint = " (the secret address was reset or the calendar is gone)" if exc.code in (401, 403, 404) else ""
        raise RuntimeError(f"HTTP {exc.code} from Google{hint}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"cannot reach Google: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"timed out after {FETCH_TIMEOUT}s") from exc
    text = body.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text[:200]:
        raise RuntimeError(f"response is not an iCalendar feed ({len(body)} bytes)")
    return text


def unfold(lines: list[str]) -> list[str]:
    """iCalendar content lines, with RFC 5545 line folding undone."""
    out: list[str] = []
    for raw in lines:
        if raw[:1] in (" ", "\t") and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


UID_RE = re.compile(r"^UID:(.*)$")
DTSTAMP_RE = re.compile(r"^DTSTAMP[^:]*:(\d{8}T\d{6}Z)$")
ATTENDEE_RE = re.compile(r"^ATTENDEE(;[^:]*)?:mailto:(.*)$", re.IGNORECASE)
PARTSTAT_RE = re.compile(r"PARTSTAT=([A-Za-z-]+)")


class Feed:
    """One split feed: vdir items keyed by UID, plus what only the raw text has.

    `partstat` is best effort. Google's iCal feeds carry no ATTENDEE line for
    the events measured here, so it is usually empty and DECLINED events cannot
    be dropped; it is filled in whenever a feed does carry attendance.
    """

    def __init__(self) -> None:
        self.items: dict[str, str] = {}
        self.partstat: dict[str, str] = {}
        self.generated_at: str | None = None
        self.count = 0


def split_feed(text: str, own: str | None) -> Feed:
    """Split one VCALENDAR into vdir items, one per UID.

    VCALENDAR-level properties and every VTIMEZONE are copied into each item;
    components sharing a UID (a recurring master and its RECURRENCE-ID
    overrides) stay in one item, which is what makes khal treat them as one
    event. METHOD is dropped: a vdir item is not an iTIP message.
    """
    header: list[str] = []
    timezones: list[str] = []
    groups: dict[str, list[str]] = {}
    feed = Feed()

    block: list[str] | None = None
    kind = ""
    depth = 0
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        # A folded continuation line is content, never a component marker: a
        # DESCRIPTION can wrap onto a line that reads "END:VEVENT" once folded.
        folded = raw[:1] in (" ", "\t")
        marker = "" if folded else raw.strip()
        if block is None:
            if marker.startswith("BEGIN:") and marker != "BEGIN:VCALENDAR":
                kind = marker.split(":", 1)[1]
                block = [raw]
                depth = 0
            elif folded or (marker and marker not in ("BEGIN:VCALENDAR", "END:VCALENDAR")):
                header.append(raw)
            continue
        block.append(raw)
        if marker.startswith("BEGIN:"):
            depth += 1
            continue
        if not marker.startswith("END:"):
            continue
        if depth:
            depth -= 1
            continue
        if kind == "VTIMEZONE":
            timezones += block
        elif kind in ("VEVENT", "VTODO", "VJOURNAL"):
            feed.count += 1
            uid = ""
            partstat = ""
            for line in unfold(block):
                found = UID_RE.match(line)
                if found:
                    uid = found.group(1).strip()
                    continue
                found = DTSTAMP_RE.match(line)
                if found:
                    stamp = found.group(1)
                    if feed.generated_at is None or stamp > feed.generated_at:
                        feed.generated_at = stamp
                    continue
                found = ATTENDEE_RE.match(line)
                if found and own and found.group(2).strip().lower() == own.lower():
                    status = PARTSTAT_RE.search(found.group(1) or "")
                    partstat = status.group(1).upper() if status else "NEEDS-ACTION"
            if not uid:
                uid = "no-uid-" + hashlib.sha1("\n".join(block).encode()).hexdigest()
            groups.setdefault(uid, []).extend(block)
            if partstat:
                feed.partstat[uid] = partstat
        block = None

    header = [line for line in unfold(header) if not line.startswith("METHOD:")]
    for uid, body in groups.items():
        feed.items[uid] = "\r\n".join(
            ["BEGIN:VCALENDAR", *header, *timezones, *body, "END:VCALENDAR", ""]
        )
    return feed


def item_filename(uid: str) -> str:
    return hashlib.sha1(uid.encode("utf-8")).hexdigest() + ".ics"


def material(data: bytes) -> bytes:
    """The part of an item that a change to the event would change.

    Google stamps DTSTAMP with the download time, so two downloads of an
    untouched calendar differ in every single event.
    """
    return b"\r\n".join(line for line in data.split(b"\r\n") if not line.startswith(b"DTSTAMP"))


def reconcile(dest: Path, label: str, items: dict[str, str]) -> tuple[int, int]:
    """Make `dest` hold exactly `items`, touching only what changed.

    khal reparses a file whose mtime moved, so rewriting an unchanged event is
    not free: it costs a reindex of the whole calendar on the next query.
    """
    dest.mkdir(parents=True, exist_ok=True)
    name = dest / "displayname"
    if not name.is_file() or name.read_text(encoding="utf-8").strip() != label:
        name.write_text(label + "\n", encoding="utf-8")

    keep = set()
    written = 0
    for uid, text in items.items():
        path = dest / item_filename(uid)
        keep.add(path.name)
        data = text.encode("utf-8")
        if path.is_file() and material(path.read_bytes()) == material(data):
            continue
        tmp = path.with_suffix(".ics.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        written += 1

    deleted = 0
    for path in dest.glob("*.ics"):
        if path.name not in keep:
            path.unlink()
            deleted += 1
    return written, deleted


def sync(sources: list[tuple[str, str]], vdir: Path, own: str | None) -> tuple[dict, dict[str, str]]:
    """Refresh the mirror. Never raises: a stale mirror still has value."""
    report: list[dict] = []
    partstat: dict[str, str] = {}
    for label, url in sources:
        try:
            feed = split_feed(fetch(url), own)
        except RuntimeError as exc:
            report.append({"label": label, "ok": False, "error": str(exc)})
            continue
        try:
            written, deleted = reconcile(vdir / label, label, feed.items)
        except OSError as exc:
            report.append({"label": label, "ok": False, "error": f"cannot write the mirror: {exc}"})
            continue
        partstat.update(feed.partstat)
        report.append(
            {
                "label": label,
                "ok": True,
                "error": None,
                "components": feed.count,
                "items": len(feed.items),
                "written": written,
                "deleted": deleted,
                "generated_at": feed.generated_at,
            }
        )
    failed = [entry["label"] for entry in report if not entry["ok"]]
    return (
        {
            "ok": bool(report) and not failed,
            "skipped": False,
            "error": f"feed fetch failed: {', '.join(failed)}" if failed else None,
            "sources": report,
        },
        partstat,
    )


def run_khal(day: str, config: str | None, calendars: list[str]) -> list[dict]:
    cmd = ["khal"]
    if config:
        cmd += ["-c", config]
    cmd += ["list", "--once"]
    for name in calendars:
        cmd += ["-a", name]
    for field in JSON_FIELDS:
        cmd += ["--json", field]
    cmd += [day, day]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"khal failed ({proc.returncode}): {(proc.stderr or '').strip()}")
    out = proc.stdout.strip()
    return json.loads(out) if out else []


def classify(title: str, categories: str, all_day: bool) -> str:
    haystack = f"{title} {categories}".lower()
    if any(w in haystack for w in LEAVE_WORDS):
        return "leave"
    if any(w in haystack for w in TRIP_WORDS):
        return "trip"
    if any(w in haystack for w in MEETING_WORDS):
        return "meeting"
    return "allday" if all_day else "event"


def normalize(row: dict, day: str, partstat: dict[str, str]) -> dict:
    all_day = row.get("all-day") == "True"
    uid = row.get("uid", "")
    return {
        "uid": uid,
        "title": row.get("title", ""),
        "start": row.get("start", ""),
        "end": row.get("end", ""),
        "all_day": all_day,
        "spans_multiple_days": all_day and row.get("start-date") != row.get("end-date"),
        "starts_today": (row.get("start-date") or row.get("start", "")[:10]) == day,
        "calendar": row.get("calendar", ""),
        "location": row.get("location", ""),
        "description": row.get("description", ""),
        "categories": row.get("categories", ""),
        "organizer": row.get("organizer", ""),
        "recurring": bool(row.get("repeat-pattern")),
        "status": row.get("status", ""),
        "partstat": partstat.get(uid, ""),
        "kind": classify(row.get("title", ""), row.get("categories", ""), all_day),
    }


def collect(day: str, args: argparse.Namespace) -> dict:
    config = Path(args.config)
    own = None
    if args.no_fetch:
        state = {"ok": False, "skipped": True, "error": None, "sources": []}
        partstat: dict[str, str] = {}
    else:
        try:
            sources = read_sources(config)
        except FileNotFoundError:
            sources = []
        if args.calendar:
            sources = [entry for entry in sources if entry[0] in args.calendar]
        own = own_address(sources)
        if sources:
            state, partstat = sync(sources, Path(args.vdir), own)
        else:
            state = {
                "ok": False,
                "skipped": False,
                "error": f"no calendars configured in {config}: run scripts/link_google_calendar.sh",
                "sources": [],
            }
            partstat = {}

    rows = run_khal(day, args.khal_config, args.calendar)
    events: list[dict] = []
    dropped = {"cancelled": 0, "declined": 0}
    for row in rows:
        event = normalize(row, day, partstat)
        if event["status"].upper() == "CANCELLED" or row.get("cancelled"):
            dropped["cancelled"] += 1
            continue
        if event["partstat"] == "DECLINED":
            dropped["declined"] += 1
            continue
        events.append(event)

    events.sort(key=lambda e: (not e["all_day"], e["start"]))
    return {
        "date": day,
        "timezone": "Asia/Seoul",
        "sync": state,
        "own_address": own,
        "calendars": sorted({e["calendar"] for e in events}),
        "events": events,
        "dropped": dropped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=kst_today(), help="KST date, YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--config",
        default=os.environ.get("DAILY_REPORT_CALENDARS", str(DEFAULT_CONFIG)),
        help="`label = secret iCal url` file (default: ~/.config/daily-report/calendars.conf)",
    )
    parser.add_argument("--no-fetch", action="store_true", help="read the local mirror without refreshing it")
    parser.add_argument("--vdir", default=str(DEFAULT_VDIR), help="local vdir root")
    parser.add_argument("--khal-config", default=None, help="khal config path (default: khal's own resolution)")
    parser.add_argument(
        "--calendar",
        action="append",
        default=[],
        help="restrict to this label; repeatable (default: all)",
    )
    args = parser.parse_args()

    result = collect(args.date, args)
    if not result["sync"]["ok"] and not result["sync"]["skipped"]:
        print(f"warning: calendar mirror not refreshed: {result['sync']['error']}", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
