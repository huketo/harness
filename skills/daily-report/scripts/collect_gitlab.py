#!/usr/bin/env python3
"""Collect today's GitLab activity for the authenticated glab user.

Outputs a structured JSON document the skill consumes when drafting
the Korean daily report: today's events (for todayWork) plus the open
issues assigned to the user (for tomorrowPlan). Group/summarize logic
intentionally lives in the skill prompt — this script only does
deterministic data fetch.

Usage:
    python collect_gitlab.py [--date YYYY-MM-DD] [--host gitlab.com]

Events default to "today" in Asia/Seoul; assigned issues are a current
snapshot and are never date-filtered. Requires `glab` CLI authenticated
to the target host. `GITLAB_HOST` can set the default host.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

KST = timezone(timedelta(hours=9))
DEFAULT_HOST = os.environ.get("GITLAB_HOST") or "gitlab.com"


def glab(host: str, path: str) -> Any:
    """Call `glab api` and return parsed JSON. Returns None on 404/empty."""
    cmd = ["glab", "api", "--hostname", host, path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"glab api {path} failed: {e.stderr}\n")
        return None
    body = out.stdout.strip()
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        sys.stderr.write(f"glab api {path} returned non-JSON: {body[:200]}\n")
        return None


def kst_today_iso() -> str:
    return datetime.now(KST).date().isoformat()


def in_kst_day(iso_utc: str, kst_day: str) -> bool:
    """True iff a UTC timestamp falls on the given KST date."""
    dt_utc = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return dt_utc.astimezone(KST).date().isoformat() == kst_day


def fetch_events(host: str, kst_day: str) -> list[dict]:
    """Fetch events that *might* fall on kst_day, then filter by KST date.

    Server-side `after` is exclusive and uses UTC dates, so we widen the
    window by one day on each side and post-filter.
    """
    after = (date.fromisoformat(kst_day) - timedelta(days=2)).isoformat()
    events: list[dict] = []
    page = 1
    while page <= 10:
        chunk = glab(host, f"events?after={after}&per_page=100&page={page}")
        if not chunk:
            break
        events.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return [e for e in events if in_kst_day(e["created_at"], kst_day)]


def lookup_project(host: str, project_id: int, cache: dict[int, dict]) -> dict:
    if project_id in cache:
        return cache[project_id]
    p = glab(host, f"projects/{project_id}") or {}
    cache[project_id] = {
        "id": project_id,
        "name": p.get("name", f"project-{project_id}"),
        "path_with_namespace": p.get("path_with_namespace", ""),
        "web_url": p.get("web_url", ""),
    }
    return cache[project_id]


MAX_COMMITS_PER_PUSH = 30


def expand_push(host: str, project_id: int, push_data: dict) -> tuple[list[dict], int]:
    """Return (commits, truncated_count). Caps long-living branch merges so a
    single push doesn't drown out same-day work — when commit_count exceeds
    MAX_COMMITS_PER_PUSH we keep only the most recent commits and report the
    overflow so the skill can label it as a bulk integration rather than
    enumerating hundreds of historical commits. Missing/null titles become empty
    strings so issue-reference matching can consume every retained commit."""
    commit_to = push_data.get("commit_to")
    commit_from = push_data.get("commit_from")
    if not commit_to:
        return [], 0
    if not commit_from or commit_from == "0000000000000000000000000000000000000000":
        return [{
            "short_id": commit_to[:8],
            "title": push_data.get("commit_title") or "",
        }], 0
    cmp_ = glab(host, f"projects/{project_id}/repository/compare?from={commit_from}&to={commit_to}")
    commits = (cmp_ or {}).get("commits", [])
    total = len(commits)
    if total > MAX_COMMITS_PER_PUSH:
        commits = commits[:MAX_COMMITS_PER_PUSH]
    out = [{"short_id": c["short_id"], "title": c.get("title") or ""} for c in commits]
    return out, max(0, total - MAX_COMMITS_PER_PUSH)


def fetch_mr(host: str, project_id: int, iid: int) -> dict:
    mr = glab(host, f"projects/{project_id}/merge_requests/{iid}") or {}
    return {
        "iid": iid,
        "title": mr.get("title"),
        "state": mr.get("state"),
        "web_url": mr.get("web_url"),
        "description": mr.get("description") or "",
    }


def fetch_issue(host: str, project_id: int, iid: int) -> dict:
    issue = glab(host, f"projects/{project_id}/issues/{iid}") or {}
    return {
        "iid": iid,
        "title": issue.get("title"),
        "state": issue.get("state"),
        "web_url": issue.get("web_url"),
    }


MAX_ASSIGNED_ISSUES = 200


def scoped_label(labels: list[str], prefix: str) -> str | None:
    """Value of the first `prefix::value` scoped label, e.g. `status::in-progress`."""
    for label in labels:
        if label.startswith(prefix):
            return label[len(prefix):]
    return None


def normalize_assigned_issue(issue: dict) -> dict:
    labels = issue.get("labels") or []
    milestone = issue.get("milestone") or None
    return {
        "ref": (issue.get("references") or {}).get("full", ""),
        "iid": issue.get("iid"),
        "project_id": issue.get("project_id"),
        "kind": issue.get("issue_type", "issue"),
        "title": issue.get("title", ""),
        "labels": labels,
        "status": scoped_label(labels, "status::"),
        "priority": scoped_label(labels, "priority::"),
        "milestone": {
            "title": milestone.get("title"),
            "due_date": milestone.get("due_date"),
            "state": milestone.get("state"),
        } if milestone else None,
        "updated_at": issue.get("updated_at"),
        "web_url": issue.get("web_url"),
        "touched_today": False,
        "evidence": [],
    }


def fetch_assigned_issues(host: str) -> list[dict]:
    """Open issues and tasks assigned to the authenticated user, newest-updated first.

    Instance-wide, so issues in projects the user pushed nothing to today are
    included. Not date-filtered: this is the tomorrow-plan backlog, not activity.
    """
    raw: list[dict] = []
    page = 1
    while len(raw) < MAX_ASSIGNED_ISSUES:
        chunk = glab(
            host,
            "issues?scope=assigned_to_me&state=opened"
            f"&order_by=updated_at&sort=desc&per_page=100&page={page}",
        )
        if not chunk:
            break
        raw.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return [normalize_assigned_issue(i) for i in raw[:MAX_ASSIGNED_ISSUES]]


def today_evidence(issue: dict, proj: dict) -> list[str]:
    """Today's events in the issue's own project that reference it.

    Replaces cross-referencing by tracker branch name: an assigned issue is
    "moved today" when a branch, commit, MR, or note names it. Commits, MR
    titles, and notes must carry an explicit `#iid`; a branch name matches on
    the iid as a dash- or slash-delimited token (`237-fix`, `feat/237`).
    """
    iid = issue["iid"]
    mention = re.compile(rf"#{iid}(?![0-9])")
    branch = re.compile(rf"(?:^|[/_-]){iid}(?:[^0-9]|$)")
    hits: list[str] = []

    for push in proj["pushes"]:
        ref = push.get("ref") or ""
        if branch.search(ref):
            hits.append(f"branch {ref}")
        for commit in push["commits"]:
            if mention.search(commit["title"]):
                hits.append(f"commit {commit['short_id']} {commit['title']}")
    for mr in proj["merge_requests"]:
        text = f"{mr.get('title') or ''}\n{(mr.get('detail') or {}).get('description', '')}"
        if mention.search(text):
            hits.append(f"MR !{mr['iid']} {mr['action']}")
    for ev in proj["issues"]:
        if ev["iid"] == iid:
            hits.append(f"issue event {ev['action']}")
    for note in proj["notes"]:
        if mention.search(f"{note.get('title') or ''}\n{note.get('note') or ''}"):
            hits.append(f"note on {note.get('title') or note['target_type']}")
    return hits


def mark_touched_today(issues: list[dict], by_project: dict[int, dict]) -> None:
    for issue in issues:
        proj = by_project.get(issue["project_id"])
        if not proj:
            continue
        evidence = today_evidence(issue, proj)
        if evidence:
            issue["touched_today"] = True
            issue["evidence"] = evidence


def collect(host: str, kst_day: str) -> dict:
    raw_events = fetch_events(host, kst_day)
    project_cache: dict[int, dict] = {}
    by_project: dict[int, dict] = {}

    for ev in raw_events:
        pid = ev["project_id"]
        proj = by_project.setdefault(pid, {
            "project": lookup_project(host, pid, project_cache),
            "pushes": [],
            "merge_requests": [],
            "issues": [],
            "notes": [],
            "other": [],
        })

        action = ev["action_name"]
        ttype = ev["target_type"]
        created_kst = (
            datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00"))
            .astimezone(KST)
            .strftime("%H:%M")
        )

        if ttype == "Project" and action.startswith("pushed"):
            push_data = ev.get("push_data", {}) or {}
            commits, truncated = expand_push(host, pid, push_data)
            proj["pushes"].append({
                "time_kst": created_kst,
                "ref": push_data.get("ref"),
                "ref_type": push_data.get("ref_type"),
                "action": push_data.get("action") or action,
                "commit_count": push_data.get("commit_count", 0),
                "commits": commits,
                "commits_truncated": truncated,
                "head_commit_title": push_data.get("commit_title"),
            })
        elif ttype == "MergeRequest":
            iid = ev["target_iid"]
            mr_detail = fetch_mr(host, pid, iid) if action in {"opened", "accepted", "approved"} else None
            proj["merge_requests"].append({
                "time_kst": created_kst,
                "action": action,
                "iid": iid,
                "title": ev.get("target_title"),
                "detail": mr_detail,
            })
        elif ttype == "Issue":
            iid = ev["target_iid"]
            proj["issues"].append({
                "time_kst": created_kst,
                "action": action,
                "iid": iid,
                "title": ev.get("target_title"),
                "detail": fetch_issue(host, pid, iid) if action == "opened" else None,
            })
        elif ttype in {"Note", "DiffNote", "DiscussionNote"}:
            proj["notes"].append({
                "time_kst": created_kst,
                "action": action,
                "target_type": ttype,
                "title": ev.get("target_title"),
                "note": (ev.get("note") or {}).get("body", "")[:400],
            })
        else:
            proj["other"].append({
                "time_kst": created_kst,
                "action": action,
                "target_type": ttype,
                "title": ev.get("target_title"),
            })

    assigned_issues = fetch_assigned_issues(host)
    mark_touched_today(assigned_issues, by_project)

    return {
        "host": host,
        "date_kst": kst_day,
        "user": (raw_events[0]["author"] if raw_events else {}),
        "event_count": len(raw_events),
        "projects": list(by_project.values()),
        "assigned_issues": assigned_issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=kst_today_iso(), help="KST date YYYY-MM-DD (default: today KST)")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"GitLab hostname (default: {DEFAULT_HOST})")
    args = parser.parse_args()
    json.dump(collect(args.host, args.date), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
