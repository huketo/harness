#!/usr/bin/env python3
"""Build a portable static comparison of catalog references and image runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
RUN_STATUSES = {"success", "error", "pending"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
STATUS_LABELS = {
    "success": "생성 완료",
    "error": "오류",
    "pending": "대기 중",
}


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{label} 파일을 찾지 못했습니다: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} JSON을 읽지 못했습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} 최상위 값은 객체여야 합니다.")
    return value


def require_schema(value: dict[str, Any], label: str) -> None:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{label}.schema_version은 {SCHEMA_VERSION}이어야 합니다.")


def require_string(value: dict[str, Any], key: str, location: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{location}.{key}는 비어 있지 않은 문자열이어야 합니다.")
    return result


def require_string_list(value: dict[str, Any], key: str, location: str) -> list[str]:
    result = value.get(key)
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise ValueError(f"{location}.{key}는 문자열 배열이어야 합니다.")
    return result


def optional_number(value: dict[str, Any], key: str, location: str) -> float | int | None:
    result = value.get(key)
    if result is None:
        return None
    if isinstance(result, bool) or not isinstance(result, (int, float)) or result < 0:
        raise ValueError(f"{location}.{key}는 0 이상의 숫자 또는 null이어야 합니다.")
    return result


def validate_catalog(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require_schema(catalog, "catalog")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise ValueError("catalog.entries는 배열이어야 합니다.")
    indexed: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        location = f"catalog.entries[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{location}는 객체여야 합니다.")
        entry_id = require_string(entry, "id", location)
        if entry_id in indexed:
            raise ValueError(f"중복 catalog entry id: {entry_id}")
        require_string(entry, "title", location)
        asset_path = entry.get("asset_path")
        if not isinstance(asset_path, str):
            raise ValueError(f"{location}.asset_path는 문자열이어야 합니다.")
        source_urls = entry.get("source_urls")
        if not isinstance(source_urls, list) or any(not isinstance(url, str) for url in source_urls):
            raise ValueError(f"{location}.source_urls는 문자열 배열이어야 합니다.")
        number = entry.get("gallery_number")
        if number is not None and (isinstance(number, bool) or not isinstance(number, int)):
            raise ValueError(f"{location}.gallery_number는 정수 또는 null이어야 합니다.")
        indexed[entry_id] = entry
    return indexed


def validate_results(results: dict[str, Any]) -> None:
    require_schema(results, "results")
    require_string(results, "title", "results")
    require_string(results, "description", "results")
    cases = results.get("cases")
    if not isinstance(cases, list):
        raise ValueError("results.cases는 배열이어야 합니다.")

    case_ids: set[str] = set()
    for case_index, case in enumerate(cases):
        location = f"results.cases[{case_index}]"
        if not isinstance(case, dict):
            raise ValueError(f"{location}는 객체여야 합니다.")
        case_id = require_string(case, "id", location)
        if case_id in case_ids:
            raise ValueError(f"중복 case id: {case_id}")
        case_ids.add(case_id)
        require_string(case, "title", location)
        require_string(case, "pattern_id", location)
        require_string(case, "short_prompt", location)
        require_string(case, "expanded_prompt", location)
        require_string_list(case, "checks", location)
        reference_ids = require_string_list(case, "reference_ids", location)
        if not 1 <= len(reference_ids) <= 3:
            raise ValueError(f"{location}.reference_ids는 1~3개여야 합니다.")

        runs = case.get("runs")
        if not isinstance(runs, list):
            raise ValueError(f"{location}.runs는 배열이어야 합니다.")
        run_ids: set[str] = set()
        for run_index, run in enumerate(runs):
            run_location = f"{location}.runs[{run_index}]"
            if not isinstance(run, dict):
                raise ValueError(f"{run_location}은 객체여야 합니다.")
            run_id = require_string(run, "id", run_location)
            if run_id in run_ids:
                raise ValueError(f"{location} 안의 중복 run id: {run_id}")
            run_ids.add(run_id)
            require_string(run, "label", run_location)
            require_string(run, "runtime", run_location)
            require_string(run, "agent_model", run_location)
            require_string(run, "image_model", run_location)
            if not isinstance(run.get("image_model_verified"), bool):
                raise ValueError(f"{run_location}.image_model_verified는 boolean이어야 합니다.")
            status = run.get("status")
            if status not in RUN_STATUSES:
                raise ValueError(
                    f"{run_location}.status는 success, error, pending 중 하나여야 합니다."
                )
            image_path = run.get("image_path")
            if image_path is not None and not isinstance(image_path, str):
                raise ValueError(f"{run_location}.image_path는 문자열 또는 null이어야 합니다.")
            optional_number(run, "elapsed_seconds", run_location)
            require_string_list(run, "notes", run_location)


def safe_name(value: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")[:42] or "item"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{readable}-{digest}"


def relative_catalog_asset(catalog_dir: Path, asset_path: str) -> tuple[Path | None, str | None]:
    if not asset_path:
        return None, "카탈로그에 복사 원본 경로가 없습니다."
    relative = PurePosixPath(asset_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None, "카탈로그 복사 원본 경로가 안전하지 않습니다."
    source = catalog_dir.joinpath(*relative.parts)
    resolved = source.resolve()
    catalog_root = catalog_dir.resolve()
    if resolved != catalog_root and catalog_root not in resolved.parents:
        return None, "카탈로그 복사 원본이 카탈로그 디렉터리 밖을 가리킵니다."
    return resolved, None


def resolve_run_image(results_dir: Path, image_path: str | None) -> Path | None:
    if not image_path:
        return None
    source = Path(image_path).expanduser()
    if not source.is_absolute():
        source = results_dir / source
    return source.resolve()


def readable_image(path: Path | None) -> tuple[bool, str | None]:
    if path is None:
        return False, "이미지 경로가 없습니다."
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return False, "지원하는 로컬 이미지 형식이 아닙니다."
    if not path.is_file():
        return False, "이미지 파일을 찾지 못했습니다."
    try:
        with path.open("rb") as stream:
            header = stream.read(32)
    except OSError:
        return False, "이미지 파일을 읽지 못했습니다."

    suffix = path.suffix.lower()
    signatures = {
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        ".gif": header.startswith((b"GIF87a", b"GIF89a")),
        ".avif": len(header) >= 12 and header[4:8] == b"ftyp" and b"avif" in header[8:32],
    }
    if not signatures.get(suffix, False):
        return False, "확장자와 이미지 파일 내용이 일치하지 않습니다."
    return True, None


def public_source_urls(entry: dict[str, Any]) -> list[str]:
    return [
        url
        for url in entry.get("source_urls", [])
        if isinstance(url, str) and url.startswith(("https://", "http://"))
    ]


def assert_assets_do_not_cover_sources(assets_root: Path, sources: list[Path]) -> None:
    resolved_assets = assets_root.resolve()
    for source in sources:
        resolved_source = source.resolve()
        if resolved_source == resolved_assets or resolved_assets in resolved_source.parents:
            raise ValueError(
                "출력 assets 디렉터리가 입력 이미지를 포함합니다. 원본을 보존하도록 다른 --output을 사용하세요."
            )


def copy_image(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def build_view_model(
    catalog: dict[str, Any],
    catalog_index: dict[str, dict[str, Any]],
    catalog_path: Path,
    results: dict[str, Any],
    results_path: Path,
    output: Path,
) -> dict[str, Any]:
    catalog_dir = catalog_path.parent.resolve()
    results_dir = results_path.parent.resolve()
    assets_root = output / "assets"
    candidate_sources: list[Path] = []

    for case in results["cases"]:
        for reference_id in case["reference_ids"]:
            entry = catalog_index.get(reference_id)
            if entry is not None:
                source, _ = relative_catalog_asset(catalog_dir, entry.get("asset_path", ""))
                if source is not None:
                    candidate_sources.append(source)
        for run in case["runs"]:
            source = resolve_run_image(results_dir, run.get("image_path"))
            if source is not None:
                candidate_sources.append(source)

    assert_assets_do_not_cover_sources(assets_root, candidate_sources)
    if assets_root.exists():
        shutil.rmtree(assets_root)

    reference_cache: dict[str, tuple[str, bool, str | None]] = {}
    view_cases: list[dict[str, Any]] = []
    for case in results["cases"]:
        anchor = f"case-{safe_name(case['id'])}"
        references: list[dict[str, Any]] = []
        for reference_id in case["reference_ids"]:
            entry = catalog_index.get(reference_id)
            if entry is None:
                references.append(
                    {
                        "id": reference_id,
                        "title": "카탈로그 항목을 찾지 못함",
                        "gallery_number": None,
                        "metadata": "",
                        "source_urls": [],
                        "image_available": False,
                        "asset_path": "",
                        "asset_issue": f"catalog id {reference_id!r}를 찾지 못했습니다.",
                    }
                )
                continue

            if reference_id not in reference_cache:
                source, path_issue = relative_catalog_asset(catalog_dir, entry.get("asset_path", ""))
                available, image_issue = readable_image(source)
                issue = path_issue or image_issue
                copied_path = ""
                if available and source is not None:
                    suffix = source.suffix.lower()
                    relative_target = PurePosixPath("assets/references") / (
                        safe_name(reference_id) + suffix
                    )
                    target = output.joinpath(*relative_target.parts)
                    copy_image(source, target)
                    copied_path = relative_target.as_posix()
                reference_cache[reference_id] = (copied_path, available, issue)
            copied_path, available, issue = reference_cache[reference_id]
            references.append(
                {
                    "id": reference_id,
                    "title": entry["title"],
                    "gallery_number": entry.get("gallery_number"),
                    "metadata": entry.get("metadata", ""),
                    "source_urls": public_source_urls(entry),
                    "image_available": available,
                    "asset_path": copied_path,
                    "asset_issue": issue,
                }
            )

        runs: list[dict[str, Any]] = []
        for run in case["runs"]:
            declared_status = run["status"]
            source = resolve_run_image(results_dir, run.get("image_path"))
            image_available, image_issue = readable_image(source)
            copied_path = ""
            if image_available and source is not None:
                suffix = source.suffix.lower()
                relative_target = (
                    PurePosixPath("assets/runs")
                    / safe_name(case["id"])
                    / (safe_name(run["id"]) + suffix)
                )
                copy_image(source, output.joinpath(*relative_target.parts))
                copied_path = relative_target.as_posix()

            effective_status = declared_status
            system_notes: list[str] = []
            if declared_status == "success" and not image_available:
                effective_status = "error"
                system_notes.append(
                    "results.json에는 success로 기록되었지만 실제 읽을 수 있는 이미지가 없어 오류로 표시합니다."
                )
            if image_issue and run.get("image_path"):
                system_notes.append(image_issue)

            runs.append(
                {
                    "id": run["id"],
                    "label": run["label"],
                    "runtime": run["runtime"],
                    "agent_model": run["agent_model"],
                    "image_model": run["image_model"],
                    "image_model_verified": run["image_model_verified"],
                    "declared_status": declared_status,
                    "status": effective_status,
                    "status_label": STATUS_LABELS[effective_status],
                    "image_available": image_available,
                    "asset_path": copied_path,
                    "elapsed_seconds": run.get("elapsed_seconds"),
                    "notes": run["notes"],
                    "system_notes": system_notes,
                }
            )

        view_cases.append(
            {
                "id": case["id"],
                "anchor": anchor,
                "title": case["title"],
                "pattern_id": case["pattern_id"],
                "short_prompt": case["short_prompt"],
                "expanded_prompt": case["expanded_prompt"],
                "checks": case["checks"],
                "references": references,
                "runs": runs,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "title": results["title"],
        "description": results["description"],
        "catalog_upstream_commit": catalog.get("upstream_commit", ""),
        "cases": view_cases,
    }


def json_for_html(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return encoded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>원본 참고 → 새 요청 적용</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f4f0e6;
      --surface: #fffdf7;
      --ink: #17252d;
      --muted: #59666b;
      --line: #c9c3b5;
      --accent: #8f351f;
      --accent-soft: #f4dfd6;
      --success: #176747;
      --success-soft: #e2f1e9;
      --error: #922f28;
      --error-soft: #f9e3df;
      --pending: #75540d;
      --pending-soft: #f7edc9;
      --focus: #005fcc;
      --shadow: 0 10px 28px rgb(32 39 42 / 10%);
    }
    * { box-sizing: border-box; }
    html { background: var(--paper); scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgb(143 53 31 / 5%) 1px, transparent 1px) 0 0 / 28px 28px,
        var(--paper);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    a { color: #71301e; text-underline-position: from-font; }
    :focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
    .skip-link {
      position: fixed;
      inset-block-start: 0.5rem;
      inset-inline-start: 0.5rem;
      z-index: 20;
      padding: 0.65rem 0.9rem;
      background: var(--ink);
      color: #fff;
      transform: translateY(-160%);
    }
    .skip-link:focus { transform: none; }
    .masthead, main { inline-size: min(1380px, calc(100% - 2rem)); margin-inline: auto; }
    .masthead { padding-block: clamp(2.5rem, 7vw, 5.5rem) 2rem; }
    .eyebrow { margin: 0 0 0.65rem; color: var(--accent); font-size: 0.78rem; font-weight: 800; letter-spacing: 0.11em; text-transform: uppercase; }
    h1 { max-inline-size: 17ch; margin: 0; font-family: ui-serif, Georgia, serif; font-size: clamp(2.35rem, 7vw, 5.1rem); line-height: 1; letter-spacing: -0.035em; }
    .lede { max-inline-size: 68ch; margin: 1.25rem 0 0; font-size: clamp(1rem, 2vw, 1.2rem); }
    .notice { max-inline-size: 78ch; margin-block-start: 1.2rem; padding-inline-start: 1rem; border-inline-start: 4px solid var(--accent); color: var(--muted); }
    main { padding-block-end: 5rem; }
    .toc { margin-block: 1rem 2rem; padding: 1rem; border: 1px solid var(--line); border-radius: 12px; background: rgb(255 253 247 / 96%); box-shadow: var(--shadow); }
    .toc h2 { margin: 0 0 0.75rem; font-size: 1rem; }
    .toc ol { display: flex; flex-wrap: wrap; gap: 0.55rem; margin: 0; padding: 0; list-style: none; }
    .toc a { display: inline-flex; min-block-size: 44px; align-items: center; gap: 0.45rem; padding: 0.55rem 0.75rem; border: 1px solid var(--line); border-radius: 8px; background: #fff; font-weight: 700; text-decoration: none; }
    .case { scroll-margin-block-start: 1rem; margin-block: 1.25rem 2.25rem; padding: clamp(1rem, 3vw, 1.5rem); border: 1px solid var(--line); border-radius: 14px; background: var(--surface); box-shadow: var(--shadow); }
    .case-header { display: grid; gap: 0.35rem; margin-block-end: 1rem; }
    .pattern { margin: 0; color: var(--accent); font-size: 0.78rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; overflow-wrap: anywhere; }
    .case h2 { margin: 0; font-family: ui-serif, Georgia, serif; font-size: clamp(1.55rem, 3vw, 2.25rem); line-height: 1.18; }
    .prompt-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; margin-block: 1rem; }
    details { min-inline-size: 0; border: 1px solid var(--line); border-radius: 9px; background: #fff; }
    summary { min-block-size: 44px; padding: 0.72rem 0.85rem; cursor: pointer; font-weight: 750; }
    pre { max-block-size: 24rem; overflow: auto; margin: 0; padding: 0.85rem; border-radius: 0 0 8px 8px; background: #1d292f; color: #f7f4ec; font: 0.8rem/1.58 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
    .checks { margin-block: 1rem 1.35rem; padding: 0.9rem 1rem; border-inline-start: 4px solid var(--accent); background: var(--accent-soft); }
    .checks h3 { margin: 0 0 0.45rem; font-size: 0.9rem; }
    .checks ul { margin: 0; padding-inline-start: 1.25rem; }
    .comparison { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr); gap: 1rem; align-items: start; }
    .group { min-inline-size: 0; }
    .group-heading { margin: 0 0 0.15rem; font-size: 1rem; }
    .group-note { margin: 0 0 0.7rem; color: var(--muted); font-size: 0.82rem; }
    .reference-grid, .run-grid { display: grid; gap: 0.75rem; }
    .reference-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr)); }
    .run-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); }
    .media-card { min-inline-size: 0; overflow: hidden; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
    .media-card.status-success { border-color: var(--success); }
    .media-card.status-error { border-color: var(--error); }
    .media-card.status-pending { border-color: #a47b18; }
    .image-link, .image-state { display: grid; inline-size: 100%; aspect-ratio: 4 / 3; place-items: center; background: #e9e5db; }
    .image-link img { inline-size: 100%; block-size: 100%; object-fit: contain; }
    .image-state { padding: 1rem; color: var(--muted); text-align: center; font-weight: 700; }
    .status-error .image-state { color: var(--error); background: var(--error-soft); }
    .status-pending .image-state { color: var(--pending); background: var(--pending-soft); }
    .media-body { display: grid; gap: 0.65rem; padding: 0.85rem; }
    .media-body h4 { margin: 0; font-size: 1rem; line-height: 1.3; overflow-wrap: anywhere; }
    .badges { display: flex; flex-wrap: wrap; gap: 0.35rem; }
    .badge { padding: 0.18rem 0.45rem; border: 1px solid var(--line); border-radius: 999px; background: #fff; color: var(--muted); font-size: 0.7rem; font-weight: 800; }
    .badge.success { border-color: var(--success); color: var(--success); background: var(--success-soft); }
    .badge.error { border-color: var(--error); color: var(--error); background: var(--error-soft); }
    .badge.pending { border-color: #a47b18; color: var(--pending); background: var(--pending-soft); }
    .badge.unknown { border-color: var(--error); color: var(--error); }
    .metadata { margin: 0; color: var(--muted); font-size: 0.78rem; overflow-wrap: anywhere; }
    dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.25rem 0.55rem; margin: 0; font-size: 0.78rem; }
    dt { color: var(--muted); font-weight: 700; }
    dd { min-inline-size: 0; margin: 0; overflow-wrap: anywhere; }
    .notes { margin: 0; padding-inline-start: 1.15rem; font-size: 0.78rem; }
    .notes.system { color: var(--error); font-weight: 650; }
    .sources { margin: 0; padding-inline-start: 1.15rem; font-size: 0.78rem; }
    .empty-runs { padding: 1.25rem; border: 1px dashed var(--line); border-radius: 10px; color: var(--muted); background: #fff; }
    .back { display: inline-flex; min-block-size: 44px; align-items: center; margin-block-start: 1rem; }
    @media (max-width: 760px) {
      .comparison, .prompt-row { grid-template-columns: 1fr; }
      .comparison { gap: 1.35rem; }
    }
    @media (max-width: 420px) {
      .masthead, main { inline-size: min(100% - 1rem, 1380px); }
      h1 { font-size: clamp(2.2rem, 15vw, 3.4rem); }
      .case { padding-inline: 0.75rem; }
      .toc ol, .toc li, .toc a { inline-size: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
    }
    @media (forced-colors: active) {
      .media-card { border: 2px solid CanvasText; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#comparison">비교 사례로 건너뛰기</a>
  <header class="masthead">
    <p id="result-title" class="eyebrow"></p>
    <h1>원본 참고 → 새 요청 적용</h1>
    <p id="result-description" class="lede"></p>
    <p class="notice">선택된 99개 원본은 취향 참고 자료입니다. 이 화면은 동일 조건의 1:1 재현이나 유사도 평가가 아니며, 모든 원본 스타일의 지원을 주장하지 않습니다. 에이전트 모델과 실제 이미지 모델은 서로 다른 항목입니다. 도구 응답으로 확인되지 않은 이미지 모델 버전은 명확히 미확인으로 표시합니다.</p>
  </header>

  <main id="comparison" tabindex="-1">
    <nav class="toc" aria-label="비교 사례 목차">
      <h2>사례 바로가기</h2>
      <ol id="toc-list"></ol>
    </nav>
    <div id="cases"></div>
  </main>

  <script id="comparison-data" type="application/json">__COMPARISON_JSON__</script>
  <script>
    (() => {
      "use strict";
      const data = JSON.parse(document.getElementById("comparison-data").textContent);
      const casesRoot = document.getElementById("cases");
      const toc = document.getElementById("toc-list");
      document.getElementById("result-title").textContent = data.title;
      document.getElementById("result-description").textContent = data.description;

      function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
      }

      function displayMetadata(value) {
        return String(value || "")
          .replace(/`/g, "")
          .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
          .replace(/<[^>]+>/g, " ")
          .replace(/\s+/g, " ")
          .trim();
      }

      function sourceLabel(url, index) {
        try {
          const parsed = new URL(url);
          return `${index === 0 ? "원본 항목" : "외부 출처"} · ${parsed.hostname}`;
        } catch (_) {
          return `출처 ${index + 1}`;
        }
      }

      function imageNode(assetPath, alt, available, stateText) {
        if (!available || !assetPath) return element("div", "image-state", stateText);
        const link = element("a", "image-link");
        link.href = assetPath;
        link.target = "_blank";
        link.rel = "noopener";
        link.setAttribute("aria-label", `${alt} 원본 이미지 확대`);
        const image = document.createElement("img");
        image.src = assetPath;
        image.alt = alt;
        image.loading = "lazy";
        image.decoding = "async";
        link.append(image);
        return link;
      }

      function referenceCard(reference) {
        const card = element("article", "media-card reference-card");
        card.append(imageNode(
          reference.asset_path,
          reference.title,
          reference.image_available,
          reference.asset_issue || "참고 이미지 없음"
        ));
        const body = element("div", "media-body");
        const badges = element("div", "badges");
        badges.append(element("span", "badge", reference.gallery_number === null ? "번호 없음" : `No. ${reference.gallery_number}`));
        body.append(badges);
        body.append(element("h4", "", reference.title));
        if (reference.metadata) body.append(element("p", "metadata", displayMetadata(reference.metadata)));
        if (reference.source_urls.length) {
          const sources = element("ul", "sources");
          reference.source_urls.forEach((url, index) => {
            const item = document.createElement("li");
            const link = element("a", "", sourceLabel(url, index));
            link.href = url;
            link.target = "_blank";
            link.rel = "noopener";
            item.append(link);
            sources.append(item);
          });
          body.append(sources);
        }
        card.append(body);
        return card;
      }

      function runImageState(run) {
        if (run.image_available) {
          if (run.status === "success") return "생성 이미지";
          return `${run.status_label} 상태의 저장된 이미지`;
        }
        if (run.status === "pending") return "결과 대기 중 · 실제 이미지 없음";
        if (run.declared_status === "success") return "성공으로 기록됐지만 실제 이미지 없음";
        return "생성 오류 · 실제 이미지 없음";
      }

      function appendDefinition(list, term, value) {
        list.append(element("dt", "", term), element("dd", "", value));
      }

      function runCard(run) {
        const card = element("article", `media-card run-card status-${run.status}`);
        card.append(imageNode(
          run.asset_path,
          `${run.label} 생성 결과`,
          run.image_available,
          runImageState(run)
        ));
        const body = element("div", "media-body");
        const badges = element("div", "badges");
        badges.append(element("span", `badge ${run.status}`, run.status_label));
        if (!run.image_model_verified) {
          badges.append(element("span", "badge unknown", "이미지 모델 버전 미확인"));
        }
        body.append(badges);
        body.append(element("h4", "", run.label));

        const facts = document.createElement("dl");
        appendDefinition(facts, "런타임", run.runtime);
        appendDefinition(facts, "에이전트 모델", run.agent_model);
        appendDefinition(facts, "이미지 모델", run.image_model);
        appendDefinition(facts, "이미지 모델 확인", run.image_model_verified ? "도구 응답으로 확인됨" : "미확인");
        appendDefinition(
          facts,
          "경과 시간",
          run.elapsed_seconds === null ? "기록 없음" : `${run.elapsed_seconds.toLocaleString("ko-KR")}초`
        );
        body.append(facts);

        if (run.notes.length) {
          const notes = element("ul", "notes");
          run.notes.forEach((note) => notes.append(element("li", "", note)));
          body.append(notes);
        }
        if (run.system_notes.length) {
          const systemNotes = element("ul", "notes system");
          run.system_notes.forEach((note) => systemNotes.append(element("li", "", note)));
          body.append(systemNotes);
        }
        card.append(body);
        return card;
      }

      function promptDetails(label, prompt) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = label;
        details.append(summary, element("pre", "", prompt));
        return details;
      }

      function buildCase(caseData) {
        const section = element("section", "case");
        section.id = caseData.anchor;
        const header = element("header", "case-header");
        header.append(element("p", "pattern", `패턴 ${caseData.pattern_id}`));
        header.append(element("h2", "", caseData.title));
        section.append(header);

        const prompts = element("div", "prompt-row");
        prompts.append(promptDetails("짧은 요청 보기", caseData.short_prompt));
        prompts.append(promptDetails("상세 요청 보기", caseData.expanded_prompt));
        section.append(prompts);

        const checks = element("section", "checks");
        checks.append(element("h3", "", "결과 체크리스트"));
        const checkList = document.createElement("ul");
        caseData.checks.forEach((check) => checkList.append(element("li", "", check)));
        checks.append(checkList);
        section.append(checks);

        const comparison = element("div", "comparison");
        const referenceGroup = element("section", "group");
        referenceGroup.append(element("h3", "group-heading", "원본 참고"));
        referenceGroup.append(element("p", "group-note", "구도와 취향을 참고한 원본이며 재현 목표나 정답 이미지가 아닙니다."));
        const referenceGrid = element("div", "reference-grid");
        caseData.references.forEach((reference) => referenceGrid.append(referenceCard(reference)));
        referenceGroup.append(referenceGrid);

        const runGroup = element("section", "group");
        runGroup.append(element("h3", "group-heading", "새 요청 적용 결과"));
        runGroup.append(element("p", "group-note", "런타임, 에이전트 모델, 실제 이미지 모델 정보를 분리해 표시합니다."));
        if (caseData.runs.length) {
          const runGrid = element("div", "run-grid");
          caseData.runs.forEach((run) => runGrid.append(runCard(run)));
          runGroup.append(runGrid);
        } else {
          runGroup.append(element("p", "empty-runs", "등록된 실행 결과가 없습니다."));
        }
        comparison.append(referenceGroup, runGroup);
        section.append(comparison);

        const back = element("a", "back", "사례 목차로 돌아가기");
        back.href = "#comparison";
        section.append(back);
        return section;
      }

      data.cases.forEach((caseData, index) => {
        const item = document.createElement("li");
        const link = element("a", "", `${index + 1}. ${caseData.title}`);
        link.href = `#${caseData.anchor}`;
        item.append(link);
        toc.append(item);
        casesRoot.append(buildCase(caseData));
      });
    })();
  </script>
</body>
</html>
'''


def build(catalog_path: Path, results_path: Path, output: Path) -> dict[str, Any]:
    catalog_path = catalog_path.resolve()
    results_path = results_path.resolve()
    output = output.resolve()
    catalog = load_json(catalog_path, "catalog")
    results = load_json(results_path, "results")
    catalog_index = validate_catalog(catalog)
    validate_results(results)
    output.mkdir(parents=True, exist_ok=True)
    view_model = build_view_model(
        catalog,
        catalog_index,
        catalog_path,
        results,
        results_path,
        output,
    )
    (output / "index.html").write_text(
        HTML_TEMPLATE.replace("__COMPARISON_JSON__", json_for_html(view_model)),
        encoding="utf-8",
    )
    print(
        f"Built comparison with {len(view_model['cases'])} cases at {output / 'index.html'}."
    )
    return view_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static Korean comparison of catalog references and image runs."
    )
    parser.add_argument("--catalog", required=True, type=Path, help="catalog.json path")
    parser.add_argument("--results", required=True, type=Path, help="results.json path")
    parser.add_argument("--output", required=True, type=Path, help="output directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build(args.catalog, args.results, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
