#!/usr/bin/env python3
"""Collect three years of one GitLab user's activity and summarize the development mix."""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "var" / "corpus" / "gitlab"
DEFAULT_HOST = os.environ.get("GITLAB_HOST") or "gitlab.com"
DEFAULT_SINCE = (date.today() - timedelta(days=3 * 365)).isoformat()
DEFAULT_UNTIL = date.today().isoformat()
PER_PAGE = 100
KST = timezone(timedelta(hours=9))
PAGE_LIMIT = 2000
# The only survivable failures: no repository access, or no repository at all.
SKIP_STATUSES = frozenset({"403", "404"})
# `all=true` makes the commits endpoint repeat page 1 forever, so a saturated
# window is bisected in time instead of paginated, down to this resolution.
COMMIT_WINDOW_FLOOR = timedelta(seconds=1)

PROJECTS_FILE = "projects.json"
COMMITS_FILE = "commits.jsonl"
MRS_FILE = "mrs.jsonl"
ISSUES_FILE = "issues.jsonl"
EVENTS_FILE = "events.jsonl"
SUMMARY_FILE = "summary.md"

# Root-level file names that decide a project's stack. A project can match
# several rows; every match counts.
STACK_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("node/bun", ("package.json", "bun.lockb", "bun.lock")),
    ("go", ("go.mod",)),
    ("rust", ("Cargo.toml",)),
    ("python", ("pyproject.toml", "requirements.txt", "setup.py")),
    ("solidity/foundry", ("foundry.toml",)),
    ("hardhat", ("hardhat.config.*",)),
    ("docker", ("Dockerfile", "docker-compose.*", "compose.y*ml")),
    ("gitlab-ci", (".gitlab-ci.yml",)),
)
UNKNOWN_STACK = "미판정"

CONVENTIONAL_TYPES = ("feat", "fix", "refactor", "docs", "chore", "test", "ci", "build", "perf", "style")
CONVENTIONAL_RE = re.compile(r"^([a-z]+)(\([^)]*\))?!?:")
OTHER_TYPE = "기타/없음"

# Korean title verbs, most specific first: a title is charged to its first hit.
KOREAN_VERBS = (
    "추가",
    "제거",
    "삭제",
    "수정",
    "정리",
    "이전",
    "도입",
    "검증",
    "개선",
    "보완",
    "분리",
    "통합",
    "복구",
    "갱신",
    "반영",
    "적용",
    "구현",
    "변경",
)
NO_VERB = "해당 없음"

SIZE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("≤20", 0, 20),
    ("21-100", 21, 100),
    ("101-500", 101, 500),
    ("501-2000", 501, 2000),
    (">2000", 2001, 10**12),
)
SCOPE_PREFIXES = ("type", "status", "priority")


class CorpusError(RuntimeError):
    pass


@dataclass
class Client:
    """`glab api` caller. Skips unreadable projects, aborts on anything else."""

    host: str
    calls: int = 0
    skipped: Counter = field(default_factory=Counter)

    def get(self, path: str, *, skippable: bool = False) -> Any | None:
        """Parsed JSON, or None when a skippable endpoint answers 403/404.

        `skippable` marks the per-project endpoints — languages, tree, commits,
        merge request detail — where 403 means "this token cannot read that
        repository" and 404 means "there is nothing there". Those are counted
        and skipped. Global listings are never skippable: a 403 or 404 on any
        page of `projects`, `merge_requests`, `issues` or `users/:id/events`
        would silently shrink the corpus, so it aborts like every other failure
        (429, 5xx, auth error, empty body, non-JSON body).
        """
        self.calls += 1
        completed = subprocess.run(
            ["glab", "api", "--hostname", self.host, path],
            capture_output=True,
            text=True,
        )
        lines = [line.strip() for line in completed.stderr.strip().splitlines() if line.strip()]
        if completed.returncode != 0:
            status = re.search(r"HTTP (\d{3})", completed.stderr)
            code = status.group(1) if status else "error"
            if not skippable or code not in SKIP_STATUSES:
                # glab wraps its errors over several lines, so keep them all.
                raise CorpusError(f"{path}: {' '.join(lines) or 'failed with no stderr'}")
            self.skipped[code] += 1
            sys.stderr.write(f"  ! {path}: {lines[-1] if lines else 'failed'} (skipped)\n")
            return None
        body = completed.stdout.strip()
        if not body:
            raise CorpusError(f"{path}: empty response body")
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise CorpusError(f"{path}: non-JSON response ({exc})") from exc

    def pages(self, path: str) -> Iterator[list[Any]]:
        """Yield pages of a global listing until an empty page arrives.

        A short page is not the end: `users/:id/events` drops events in
        projects the caller cannot read after paginating. A filtered page
        can be short even when later pages still contain visible events.
        Stopping on a short page would silently truncate the corpus.
        Listings are not skippable, so any failed page — including one in the
        middle — aborts and a truncated listing can never pass for a complete
        one.
        """
        page = 1
        while True:
            chunk = self.get(with_query(path, f"per_page={PER_PAGE}&page={page}"))
            if not chunk:
                return
            if not isinstance(chunk, list):
                raise CorpusError(f"expected a list from {path}, got {type(chunk).__name__}")
            yield chunk
            page += 1
            if page > PAGE_LIMIT:
                raise CorpusError(f"{path} still paginating past page {PAGE_LIMIT}")

    def collect_all(self, path: str) -> list[Any]:
        return [item for chunk in self.pages(path) for item in chunk]


def with_query(path: str, extra: str) -> str:
    return f"{path}{'&' if '?' in path else '?'}{extra}"


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def kst_year(value: str) -> str:
    return str(parse_iso(value).astimezone(KST).year)


# ---------------------------------------------------------------- collect


def fetch_projects(client: Client) -> list[dict[str, Any]]:
    raw = client.collect_all("projects?membership=true")
    projects: list[dict[str, Any]] = []
    for index, project in enumerate(raw, start=1):
        project_id = project["id"]
        languages = client.get(f"projects/{project_id}/languages", skippable=True)
        tree = client.get(f"projects/{project_id}/repository/tree?per_page={PER_PAGE}", skippable=True)
        projects.append(
            {
                "id": project_id,
                "path_with_namespace": project.get("path_with_namespace", ""),
                "archived": bool(project.get("archived")),
                "last_activity_at": project.get("last_activity_at", ""),
                "default_branch": project.get("default_branch"),
                "languages": languages if isinstance(languages, dict) else {},
                "root_files": [entry["name"] for entry in tree] if isinstance(tree, list) else [],
            }
        )
        sys.stderr.write(f"[{index}/{len(raw)}] project {project_id} metadata\n")
    return projects


def fetch_project_commits(client: Client, project_id: int, user: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Author-filtered commits across all refs in the inclusive window.

    Measured 2026-09-05: `all=true` walks every ref and ignores `page` — pages
    1, 2 and 3 of one project returned the same 100 commits, while the same
    query without `all=true` paginated correctly, so a project with more than
    `PER_PAGE` matching commits cannot be paginated (11 projects were truncated
    at exactly 100 before this).

    Each request therefore asks for page 1 only, and a saturated window is
    bisected in time until it is not. Sub-windows touch at their boundary
    instant, so nothing falls between them; the `id` map drops the duplicate.
    A window still saturated at one second cannot be narrowed further, so it
    would hide commits: that aborts the run instead of returning short.
    """
    found: dict[str, dict[str, Any]] = {}
    pending = [(start, end)]
    while pending:
        window_start, window_end = pending.pop()
        since = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        until = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        chunk = client.get(
            f"projects/{project_id}/repository/commits?author={user}"
            f"&since={since}&until={until}"
            f"&with_stats=true&all=true&per_page={PER_PAGE}&page=1",
            skippable=True,
        )
        if not chunk:
            continue
        for commit in chunk:
            found.setdefault(commit["id"], commit)
        if len(chunk) < PER_PAGE:
            continue
        if window_end - window_start <= COMMIT_WINDOW_FLOOR:
            raise CorpusError(
                f"project {project_id}: {PER_PAGE} commits in the one-second window {since}..{until}; "
                "the window cannot be narrowed further, so the corpus would be incomplete"
            )
        middle = (window_start + (window_end - window_start) / 2).replace(microsecond=0)
        pending.append((window_start, middle))
        pending.append((middle, window_end))
    return list(found.values())


def fetch_commits(client: Client, projects: Sequence[dict[str, Any]], user: str, since: str, until: str) -> list[dict[str, Any]]:
    """One row per commit id across every project.

    Forks and mirrors can carry the same commit id in several projects.
    Record each commit against the first project in which it is seen.
    """
    start = datetime.fromisoformat(f"{since}T00:00:00+00:00")
    end = datetime.fromisoformat(f"{until}T23:59:59+00:00")
    commits: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0
    for index, project in enumerate(projects, start=1):
        project_id = project["id"]
        recorded = 0
        for commit in fetch_project_commits(client, project_id, user, start, end):
            commit_id = commit["id"]
            if commit_id in seen:
                duplicates += 1
                continue
            seen.add(commit_id)
            recorded += 1
            stats = commit.get("stats") or {}
            commits.append(
                {
                    "project": project_id,
                    "id": commit_id,
                    "created_at": commit.get("created_at", ""),
                    "title": commit.get("title", ""),
                    "additions": int(stats.get("additions") or 0),
                    "deletions": int(stats.get("deletions") or 0),
                    "total": int(stats.get("total") or 0),
                }
            )
        sys.stderr.write(f"[{index}/{len(projects)}] project {project_id} commits={recorded}\n")
    if duplicates:
        sys.stderr.write(f"commits already recorded under another project: {duplicates}\n")
    return commits


def fetch_merge_requests(client: Client, user: str, since: str) -> list[dict[str, Any]]:
    listed = client.collect_all(f"merge_requests?scope=all&author_username={user}&created_after={since}T00:00:00Z")
    merge_requests: list[dict[str, Any]] = []
    for index, mr in enumerate(listed, start=1):
        project_id = mr["project_id"]
        iid = mr["iid"]
        # `changes_count` exists only on the detail endpoint.
        detail = client.get(f"projects/{project_id}/merge_requests/{iid}", skippable=True) or {}
        merge_requests.append(
            {
                "project": project_id,
                "iid": iid,
                "title": mr.get("title", ""),
                "state": mr.get("state", ""),
                "created_at": mr.get("created_at", ""),
                "merged_at": mr.get("merged_at"),
                "changes_count": detail.get("changes_count"),
                "labels": mr.get("labels") or [],
                "source_branch": mr.get("source_branch", ""),
                "target_branch": mr.get("target_branch", ""),
                "user_notes_count": mr.get("user_notes_count", 0),
            }
        )
        if index % 50 == 0 or index == len(listed):
            sys.stderr.write(f"[{index}/{len(listed)}] merge request details\n")
    return merge_requests


def fetch_issues(client: Client, user: str, since: str) -> list[dict[str, Any]]:
    roles = (
        ("author", f"issues?scope=all&author_username={user}&created_after={since}T00:00:00Z"),
        ("assignee", f"issues?scope=all&assignee_username={user}&created_after={since}T00:00:00Z"),
    )
    merged: dict[tuple[int, int], dict[str, Any]] = {}
    for role, query in roles:
        found = 0
        for issue in client.collect_all(query):
            key = (issue["project_id"], issue["iid"])
            found += 1
            existing = merged.get(key)
            if existing is not None:
                if existing["role"] != role:
                    existing["role"] = "both"
                continue
            merged[key] = {
                "project": issue["project_id"],
                "iid": issue["iid"],
                "title": issue.get("title", ""),
                "state": issue.get("state", ""),
                "created_at": issue.get("created_at", ""),
                "closed_at": issue.get("closed_at"),
                "labels": issue.get("labels") or [],
                "author": (issue.get("author") or {}).get("username", ""),
                "assignees": [a.get("username", "") for a in issue.get("assignees") or []],
                "role": role,
            }
        sys.stderr.write(f"issues as {role}: {found}\n")
    return list(merged.values())


def fetch_events(client: Client, user_id: int, since: str, until: str) -> list[dict[str, Any]]:
    after = (date.fromisoformat(since) - timedelta(days=1)).isoformat()
    before = (date.fromisoformat(until) + timedelta(days=1)).isoformat()
    events: list[dict[str, Any]] = []
    for event in client.collect_all(f"users/{user_id}/events?after={after}&before={before}"):
        push = event.get("push_data") or {}
        record = {
            "created_at": event.get("created_at", ""),
            "action_name": event.get("action_name", ""),
            "target_type": event.get("target_type"),
            "project_id": event.get("project_id"),
        }
        if push:
            record["push_data"] = {
                "commit_count": push.get("commit_count"),
                "ref": push.get("ref"),
                "action": push.get("action"),
            }
        events.append(record)
    sys.stderr.write(f"events: {len(events)}\n")
    return events


def resolve_user_id(client: Client, user: str) -> int:
    matches = client.get(f"users?username={user}")
    if not matches:
        raise CorpusError(f"user {user} not found on {client.host}")
    return int(matches[0]["id"])


def resolve_identity(client: Client, user: str | None) -> tuple[str, int]:
    """Resolve an explicit username or the account authenticated by glab."""
    if user:
        return user, resolve_user_id(client, user)
    account = client.get("user")
    if not isinstance(account, dict):
        raise CorpusError(f"authenticated user response from {client.host} is not an object")
    username = account.get("username")
    user_id = account.get("id")
    if not isinstance(username, str) or not username or not isinstance(user_id, int):
        raise CorpusError(f"authenticated user response from {client.host} lacks username or id")
    return username, user_id


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def command_collect(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    client = Client(args.host)
    user, user_id = resolve_identity(client, args.user)

    projects = fetch_projects(client)
    (out / PROJECTS_FILE).write_text(json.dumps(projects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    commits = fetch_commits(client, projects, user, args.since, args.until)
    write_jsonl(out / COMMITS_FILE, commits)

    merge_requests = fetch_merge_requests(client, user, args.since)
    write_jsonl(out / MRS_FILE, merge_requests)

    issues = fetch_issues(client, user, args.since)
    write_jsonl(out / ISSUES_FILE, issues)

    events = fetch_events(client, user_id, args.since, args.until)
    write_jsonl(out / EVENTS_FILE, events)

    sys.stderr.write(
        f"done: {len(projects)} projects, {len(commits)} commits, {len(merge_requests)} merge requests, "
        f"{len(issues)} issues, {len(events)} events in {client.calls} calls\n"
    )
    if client.skipped:
        sys.stderr.write(f"skipped calls: {dict(sorted(client.skipped.items()))}\n")
    return 0


# ---------------------------------------------------------------- analyze


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise CorpusError(f"missing {path}; run `collect` first")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"invalid JSON in {path}: {exc}") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CorpusError(f"missing {path}; run `collect` first")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise CorpusError(f"invalid JSON on {path}:{number}: {exc}") from exc
    return rows


def unique_commits(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per commit id, keeping the first project that recorded it.

    A corpus collected before the fetcher deduplicated across projects holds
    the same commit once per fork or mirror, which would double-count it in
    every distribution here.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_id.setdefault(row["id"], row)
    dropped = len(rows) - len(by_id)
    if dropped:
        sys.stderr.write(f"ignored {dropped} commit rows already recorded under another project\n")
    return list(by_id.values())


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return lines


def pct(part: float, whole: float) -> str:
    return "-" if whole <= 0 else f"{part / whole * 100:.1f}%"


def percentile(values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile. Empty input yields 0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return float(ordered[index])


def changes_count(value: Any) -> tuple[int, bool] | None:
    """`(files, capped)` from a `changes_count` string, or None when absent.

    GitLab caps the value at the MR's diff limit and marks it with a `+`
    suffix (`"54+"`, `"1000+"`): those rows only give a lower bound, so size
    statistics drop them instead of understating the change.
    """
    if value is None:
        return None
    text = str(value).strip()
    digits = re.match(r"\d+", text)
    if not digits:
        return None
    return int(digits.group()), text.endswith("+")


def stacks_for(root_files: Sequence[str]) -> list[str]:
    hits = [
        stack
        for stack, patterns in STACK_MARKERS
        if any(fnmatch.fnmatch(name, pattern) for name in root_files for pattern in patterns)
    ]
    return hits or [UNKNOWN_STACK]


def conventional_type(title: str) -> str:
    match = CONVENTIONAL_RE.match(title.strip().lower())
    if match and match.group(1) in CONVENTIONAL_TYPES:
        return match.group(1)
    return OTHER_TYPE


def korean_verb(title: str) -> str:
    for verb in KOREAN_VERBS:
        if verb in title:
            return verb
    return NO_VERB


def size_table(label: str, unit: str, values: Sequence[int]) -> list[str]:
    lines = [
        f"{label} 표본 {len(values)}건, p50 {percentile(values, 0.50):.0f} / "
        f"p90 {percentile(values, 0.90):.0f} / p99 {percentile(values, 0.99):.0f} {unit}",
        "",
    ]
    rows = []
    for name, low, high in SIZE_BUCKETS:
        count = sum(1 for value in values if low <= value <= high)
        rows.append([name, count, pct(count, len(values))])
    lines.extend(md_table(["구간", "건수", "비율"], rows))
    return lines


def type_table(label: str, titles: Sequence[str], classify) -> list[str]:
    counts = Counter(classify(title) for title in titles)
    rows = [[name, count, pct(count, len(titles))] for name, count in counts.most_common()]
    return [f"{label} 표본 {len(titles)}건", ""] + md_table(["유형", "건수", "비율"], rows)


def section_scope(
    projects: Sequence[dict[str, Any]],
    commits: Sequence[dict[str, Any]],
    merge_requests: Sequence[dict[str, Any]],
    issues: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    commits_by_project: Counter,
) -> list[str]:
    with_commits = sum(1 for project in projects if commits_by_project[project["id"]] > 0)
    touched = (
        {commit["project"] for commit in commits}
        | {mr["project"] for mr in merge_requests}
        | {issue["project"] for issue in issues}
        | {event["project_id"] for event in events if event["project_id"] is not None}
    )
    archived = sum(1 for project in projects if project["archived"])
    lines = [
        "## 1. 수집 범위",
        "",
        *md_table(
            ["항목", "값"],
            [
                ["프로젝트(멤버십 전체)", len(projects)],
                ["프로젝트(활동 있음: 커밋·MR·이슈·이벤트)", len(touched)],
                ["프로젝트(사용자 커밋 있음)", with_commits],
                ["프로젝트(보관됨)", archived],
                ["커밋", len(commits)],
                ["머지 리퀘스트", len(merge_requests)],
                ["이슈", len(issues)],
                ["이벤트", len(events)],
            ],
        ),
        "",
        "'활동 있음'은 네 자료에 나타난 프로젝트 ID의 합집합이므로 멤버십 목록 밖의 프로젝트도 들어올 수 있다"
        f"(이번 수집에서는 {len(touched & {project['id'] for project in projects})}개가 멤버십 안에 있다).",
        "",
        "연도별 커밋(KST):",
        "",
    ]
    per_year = Counter(kst_year(commit["created_at"]) for commit in commits if commit["created_at"])
    lines.extend(
        md_table(
            ["연도", "커밋", "비율"],
            [[year, count, pct(count, len(commits))] for year, count in sorted(per_year.items())],
        )
    )
    return lines


def section_languages(projects: Sequence[dict[str, Any]], commits_by_project: Counter) -> list[str]:
    weighted: Counter = Counter()
    for project in projects:
        weight = commits_by_project[project["id"]]
        if weight <= 0:
            continue
        for language, share in project["languages"].items():
            weighted[language] += float(share) * weight
    total = sum(weighted.values())
    rows = [[language, f"{value:.0f}", pct(value, total)] for language, value in weighted.most_common(15)]
    return [
        "## 2. 언어 분포",
        "",
        f"프로젝트 언어 비율 × 그 프로젝트의 사용자 커밋 수를 합산한 가중치. 언어 {len(weighted)}종 중 상위 15개.",
        "",
        *md_table(["언어", "가중치", "비율"], rows),
    ]


def section_stacks(projects: Sequence[dict[str, Any]], commits_by_project: Counter) -> list[str]:
    project_counts: Counter = Counter()
    commit_counts: Counter = Counter()
    for project in projects:
        for stack in stacks_for(project["root_files"]):
            project_counts[stack] += 1
            commit_counts[stack] += commits_by_project[project["id"]]
    rows = [
        [stack, project_counts[stack], commit_counts[stack], pct(commit_counts[stack], sum(commits_by_project.values()))]
        for stack, _ in commit_counts.most_common()
    ]
    return [
        "## 3. 스택 분포",
        "",
        "최상위 파일로 판정. 한 프로젝트가 여러 스택에 속할 수 있어 합계는 프로젝트 수를 넘는다.",
        "",
        *md_table(["스택", "프로젝트", "커밋", "커밋 비율"], rows),
    ]


def mr_file_counts(merge_requests: Sequence[dict[str, Any]]) -> tuple[list[int], int, int]:
    """Exact file counts, plus the capped and missing row counts."""
    exact: list[int] = []
    capped = 0
    missing = 0
    for mr in merge_requests:
        parsed = changes_count(mr["changes_count"])
        if parsed is None:
            missing += 1
        elif parsed[1]:
            capped += 1
        else:
            exact.append(parsed[0])
    return exact, capped, missing


def section_sizes(commits: Sequence[dict[str, Any]], merge_requests: Sequence[dict[str, Any]]) -> list[str]:
    commit_sizes = [int(commit["total"]) for commit in commits]
    mr_sizes, capped, missing = mr_file_counts(merge_requests)
    lines = ["## 4. 변경 크기", "", "### 커밋 변경 줄 수", ""]
    lines.extend(size_table("커밋", "줄", commit_sizes))
    lines.extend(["", "### MR 변경 파일 수(`changes_count`)", ""])
    lines.append(
        f"전체 MR {len(merge_requests)}건 중 capped {capped}건(`54+`처럼 하한만 알려짐)과 값 없음 {missing}건을 통계에서 제외했다."
    )
    lines.append("")
    lines.extend(size_table("MR", "개", mr_sizes))
    return lines


def section_types(commits: Sequence[dict[str, Any]], merge_requests: Sequence[dict[str, Any]]) -> list[str]:
    commit_titles = [commit["title"] for commit in commits]
    mr_titles = [mr["title"] for mr in merge_requests]
    lines = ["## 5. 변경 유형", "", "### conventional 접두어 — 커밋", ""]
    lines.extend(type_table("커밋", commit_titles, conventional_type))
    lines.extend(["", "### conventional 접두어 — MR", ""])
    lines.extend(type_table("MR", mr_titles, conventional_type))
    lines.extend(["", "### 한국어 제목 동사(커밋 + MR)", ""])
    lines.extend(type_table("제목", commit_titles + mr_titles, korean_verb))
    return lines


def section_issues(issues: Sequence[dict[str, Any]]) -> list[str]:
    states = Counter(issue["state"] for issue in issues)
    roles = Counter(issue["role"] for issue in issues)
    lines = [
        "## 6. 이슈",
        "",
        *md_table(
            ["상태/역할", "건수", "비율"],
            [[name, count, pct(count, len(issues))] for name, count in list(states.most_common()) + list(roles.most_common())],
        ),
        "",
    ]
    for prefix in SCOPE_PREFIXES:
        counts: Counter = Counter()
        for issue in issues:
            values = [label.split("::", 1)[1] for label in issue["labels"] if label.startswith(f"{prefix}::")]
            counts.update(values or ["(없음)"])
        lines.extend([f"`{prefix}::*` 라벨:", ""])
        lines.extend(
            md_table(
                ["값", "건수", "비율"],
                [[value, count, pct(count, len(issues))] for value, count in counts.most_common()],
            )
        )
        lines.append("")
    durations = [
        (parse_iso(issue["closed_at"]) - parse_iso(issue["created_at"])).total_seconds() / 86400
        for issue in issues
        if issue.get("closed_at") and issue.get("created_at")
    ]
    lines.append(
        f"생성→종료 소요일(종료 {len(durations)}건): p50 {percentile(durations, 0.50):.1f}일 / "
        f"p90 {percentile(durations, 0.90):.1f}일"
    )
    return lines


def section_activity(events: Sequence[dict[str, Any]]) -> list[str]:
    per_year: dict[str, Counter] = defaultdict(Counter)
    overall: Counter = Counter()
    for event in events:
        if not event["created_at"]:
            continue
        action = event["action_name"] or "(없음)"
        overall[action] += 1
        per_year[kst_year(event["created_at"])][action] += 1
    years = sorted(per_year)
    rows = []
    for action, count in overall.most_common():
        row: list[Any] = [action, count, pct(count, len(events))]
        row.extend(pct(per_year[year][action], sum(per_year[year].values())) for year in years)
        rows.append(row)
    pushes = [event["push_data"]["commit_count"] or 0 for event in events if event.get("push_data")]
    stamps = sorted(event["created_at"] for event in events if event["created_at"])
    span = f"{stamps[0][:10]} .. {stamps[-1][:10]}" if stamps else "없음"
    return [
        "## 7. 활동 형태",
        "",
        f"수집된 이벤트의 실제 기간: {span}. 연도별 비율은 각 연도 안에서 정규화한 값이다.",
        "",
        *md_table(["action_name", "건수", "전체 비율", *(f"{year} 비율" for year in years)], rows),
        "",
        f"push 이벤트 {len(pushes)}건의 커밋 수: p50 {percentile(pushes, 0.50):.0f} / p90 {percentile(pushes, 0.90):.0f} / "
        f"최대 {max(pushes) if pushes else 0}",
    ]


def section_projects(
    projects: Sequence[dict[str, Any]],
    commits_by_project: Counter,
    mrs_by_project: Counter,
) -> list[str]:
    by_id = {project["id"]: project for project in projects}
    top = commits_by_project.most_common(20)
    rows = []
    for project_id, count in top:
        project = by_id.get(project_id, {})
        languages = project.get("languages") or {}
        primary = max(languages, key=languages.get) if languages else "-"
        rows.append(
            [
                project.get("path_with_namespace") or f"project-{project_id}",
                count,
                mrs_by_project[project_id],
                primary,
            ]
        )
    return [
        "## 8. 프로젝트 상위 20개",
        "",
        "이 절은 `var/` 밖으로 옮기지 않는다(회사 자료).",
        "",
        *md_table(["프로젝트", "커밋", "MR", "주 언어"], rows),
    ]


def section_design_note(
    projects: Sequence[dict[str, Any]],
    commits: Sequence[dict[str, Any]],
    merge_requests: Sequence[dict[str, Any]],
    issues: Sequence[dict[str, Any]],
    commits_by_project: Counter,
) -> list[str]:
    weighted: Counter = Counter()
    for project in projects:
        weight = commits_by_project[project["id"]]
        for language, share in project["languages"].items():
            weighted[language] += float(share) * weight
    top_three = weighted.most_common(3)
    top_languages = ", ".join(f"{name} {pct(value, sum(weighted.values()))}" for name, value in top_three) or "없음"
    commit_sizes = [int(commit["total"]) for commit in commits]
    mr_sizes = mr_file_counts(merge_requests)[0]
    small = sum(1 for value in commit_sizes if value <= 100)
    modal_bucket = max(
        SIZE_BUCKETS,
        key=lambda bucket: sum(1 for value in commit_sizes if bucket[1] <= value <= bucket[2]),
    )[0]
    commit_types = Counter(conventional_type(commit["title"]) for commit in commits)
    top_types = ", ".join(f"{name} {pct(count, len(commits))}" for name, count in commit_types.most_common(3))
    active_projects = sum(1 for project in projects if commits_by_project[project["id"]] > 0)
    typed = sum(1 for commit in commits if conventional_type(commit["title"]) != OTHER_TYPE)
    closed = sum(1 for issue in issues if issue["state"] == "closed")
    return [
        "## 9. 벤치마크 설계 메모",
        "",
        f"과제 언어는 가중치 상위 세 항목({top_languages})에 맞춰 배분하면 실제 작업의 대부분을 덮는다. "
        f"활동이 있는 프로젝트는 {active_projects}개뿐이고 언어 가중치가 여기 몰려 있다.",
        f"커밋 변경 줄 수는 p50 {percentile(commit_sizes, 0.50):.0f}줄, p90 {percentile(commit_sizes, 0.90):.0f}줄이고 "
        f"최다 구간이 {modal_bucket}줄(100줄 이하는 {pct(small, len(commit_sizes))})이므로, "
        f"과제 하나는 파일 몇 개에 걸친 {modal_bucket}줄 규모를 중심에 두고 2000줄을 넘기는 대형 변경은 소수만 넣는다.",
        f"MR 단위 규모는 변경 파일 p50 {percentile(mr_sizes, 0.50):.0f}개, p90 {percentile(mr_sizes, 0.90):.0f}개이므로, "
        f"한 과제가 건드릴 파일 수의 상한도 그 범위에서 정한다.",
        f"유형 비중은 {top_types} 순이고 제목에 conventional 접두어가 붙은 커밋이 "
        f"{pct(typed, len(commits))}이므로, 과제 부류도 기능 추가·버그 수정·리팩터링·문서/설정 정리로 나누고 같은 비율로 표본을 뽑는다.",
        f"이슈 {len(issues)}건 중 {pct(closed, len(issues))}가 종료되었고 스코프 라벨이 유형과 우선순위를 함께 담으므로, "
        "과제 명세는 이슈 본문처럼 목표와 수용 기준을 갖춘 형태로 쓰고 검증은 이슈 종료 조건에 대응시킨다.",
    ]


def command_analyze(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    projects = load_json(out / PROJECTS_FILE)
    commits = unique_commits(load_jsonl(out / COMMITS_FILE))
    merge_requests = load_jsonl(out / MRS_FILE)
    issues = load_jsonl(out / ISSUES_FILE)
    events = load_jsonl(out / EVENTS_FILE)

    commits_by_project: Counter = Counter(commit["project"] for commit in commits)
    mrs_by_project: Counter = Counter(mr["project"] for mr in merge_requests)

    sections = [
        [
            "# GitLab 개발 활동 분포",
            "",
            f"생성 시각(KST): {datetime.now(KST).isoformat(timespec='seconds')}",
            f"원자료: `{out}`",
        ],
        section_scope(projects, commits, merge_requests, issues, events, commits_by_project),
        section_languages(projects, commits_by_project),
        section_stacks(projects, commits_by_project),
        section_sizes(commits, merge_requests),
        section_types(commits, merge_requests),
        section_issues(issues),
        section_activity(events),
        section_projects(projects, commits_by_project, mrs_by_project),
        section_design_note(projects, commits, merge_requests, issues, commits_by_project),
    ]
    body = "\n\n".join("\n".join(section).strip("\n") for section in sections) + "\n"
    (out / SUMMARY_FILE).write_text(body, encoding="utf-8")
    sys.stderr.write(f"wrote {out / SUMMARY_FILE}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="download the activity corpus through glab")
    collect_parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"GitLab hostname known to glab (default: {DEFAULT_HOST})"
    )
    collect_parser.add_argument(
        "--user",
        help="GitLab username to collect (default: account authenticated by glab for --host)",
    )
    collect_parser.add_argument("--since", default=DEFAULT_SINCE, help="first day of the window, YYYY-MM-DD")
    collect_parser.add_argument("--until", default=DEFAULT_UNTIL, help="last day of the window, YYYY-MM-DD")
    collect_parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    collect_parser.set_defaults(handler=command_collect)

    analyze_parser = subparsers.add_parser("analyze", help="write summary.md from a collected corpus")
    analyze_parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="directory holding the collected corpus")
    analyze_parser.set_defaults(handler=command_analyze)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
