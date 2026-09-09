#!/usr/bin/env python3
"""Build a portable, static catalog from the GPT Image 2 prompt gallery."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import quote

SCHEMA_VERSION = 1
README_SHOWCASE_HEADING = "## 🎨 Prompt Showcase"
README_SHOWCASE_END = "## 🙏 Acknowledgments"
MISSING_PROMPT = ""
MISSING_METADATA = ""

CATEGORY_LABELS = {
    "Anime & Manga": "애니메이션·만화",
    "Gaming": "게임",
    "Retro & Cyberpunk": "레트로·사이버펑크",
    "Cinematic & Animation": "시네마틱·애니메이션",
    "Character Design": "캐릭터 디자인",
    "Typography & Posters": "타이포그래피·포스터",
    "Illustration": "일러스트레이션",
    "Watercolor": "수채화",
    "Ink & Chinese": "수묵·중화권 스타일",
    "Pixel Art": "픽셀 아트",
    "Isometric": "아이소메트릭",
    "Product & Food": "제품·음식",
    "Brand Systems & Identity": "브랜드 시스템·아이덴티티",
    "Photography": "사진",
    "Infographics & Field Guides": "인포그래픽·필드 가이드",
    "Research Paper Figures": "연구 논문 도판",
    "Official OpenAI Cookbook Examples": "OpenAI Cookbook 공식 예제",
    "Edit Endpoint Showcase": "편집 엔드포인트 쇼케이스",
    "UI/UX Mockups": "UI/UX 목업",
    "Data Visualization": "데이터 시각화",
    "Technical Illustration": "기술 일러스트레이션",
    "Architecture & Interior": "건축·인테리어",
    "Scientific & Educational": "과학·교육",
    "Fashion Editorial": "패션 에디토리얼",
    "Fine Art Painting": "순수 회화",
    "More Illustration Styles": "추가 일러스트 스타일",
    "Cinematic Film References": "영화적 레퍼런스",
    "Beauty & Lifestyle": "뷰티·라이프스타일",
    "Events & Experience": "이벤트·경험",
    "Tattoo Design": "타투 디자인",
    "Screen Photography": "화면 사진",
}

ENTRY_HEADING_RE = re.compile(r"^### No\. (\d+) · (.+)$", re.MULTILINE)
METADATA_RE = re.compile(r"^- Metadata: (.*)$", re.MULTILINE)
PROMPT_RE = re.compile(r"```text\n(.*?)\n```", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
PLAIN_URL_RE = re.compile(r"https?://[^\s)>]+")
LOCAL_IMAGE_RE = re.compile(r"^docs/.+\.(?:png|jpe?g|webp)$", re.IGNORECASE)
HTML_IMAGE_RE = re.compile(r"<img\b([^>]*?)>", re.IGNORECASE | re.DOTALL)
HTML_ATTR_RE = re.compile(r"\b(src|alt)=[\"']([^\"']*)[\"']", re.IGNORECASE)


def run_git(upstream: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(upstream), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise RuntimeError(f"원본 저장소 Git 정보를 읽지 못했습니다: {detail.strip()}") from exc
    return result.stdout.strip()


def normalize_remote(remote: str) -> str:
    remote = remote.removesuffix(".git")
    match = re.fullmatch(r"git@([^:]+):(.+)", remote)
    if match:
        return f"https://{match.group(1)}/{match.group(2)}"
    match = re.fullmatch(r"ssh://git@([^/]+)/(.+)", remote)
    if match:
        return f"https://{match.group(1)}/{match.group(2)}"
    return remote


def strip_inline_markdown(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("`", "").replace("*", "").replace("_", "")
    return html.unescape(value).strip()


def strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " · ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def safe_repo_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"안전하지 않은 원본 상대 경로: {value}")
    return path


def source_url(
    upstream_url: str,
    commit: str,
    relative_path: str,
    first_line: int,
    last_line: int | None = None,
) -> str:
    if not upstream_url.startswith(("https://", "http://")):
        return upstream_url
    anchor = f"#L{first_line}"
    if last_line is not None and last_line != first_line:
        anchor += f"-L{last_line}"
    return f"{upstream_url}/blob/{commit}/{quote(relative_path, safe='/')}{anchor}"


def unique_urls(*groups: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            if value and value not in seen:
                result.append(value)
                seen.add(value)
    return result


def extract_urls(value: str) -> list[str]:
    markdown_urls = MARKDOWN_LINK_RE.findall(value)
    plain_urls = [url for url in PLAIN_URL_RE.findall(value) if url not in markdown_urls]
    return unique_urls(markdown_urls, plain_urls)


def parse_declared_images(body: str) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    singular = re.search(r"^- Image: `([^`]+)`", body, re.MULTILINE)
    if singular:
        images.append(
            {
                "image_path": singular.group(1),
                "label": "대표 이미지",
                "kind": "primary",
            }
        )

    plural = re.search(r"^- Images:\s*$", body, re.MULTILINE)
    if plural:
        for match in re.finditer(r"^  - `([^`]+)`(?:\s+—\s+(.+))?$", body, re.MULTILINE):
            images.append(
                {
                    "image_path": match.group(1),
                    "label": (match.group(2) or "갤러리 이미지").strip(),
                    "kind": "gallery_image",
                }
            )

    for match in re.finditer(r"^- Input image: `([^`]+)`", body, re.MULTILINE):
        images.append(
            {
                "image_path": match.group(1),
                "label": "입력 이미지",
                "kind": "input",
            }
        )

    if not images:
        fallback = re.search(r"`(docs/[^`]+\.(?:png|jpe?g|webp))`", body, re.IGNORECASE)
        if fallback:
            images.append(
                {
                    "image_path": fallback.group(1),
                    "label": "원본에 표시된 이미지",
                    "kind": "fallback",
                }
            )
    return images


def choose_primary(images: list[dict[str, str]]) -> dict[str, str] | None:
    for image in images:
        if image["kind"] == "primary":
            return image
    if images:
        # Plural edit showcases list the input first and the resulting image last.
        return images[-1]
    return None


def parse_showcase(readme: str) -> tuple[str, list[dict[str, object]]]:
    try:
        start = readme.index(README_SHOWCASE_HEADING)
    except ValueError as exc:
        raise ValueError(f"README에 {README_SHOWCASE_HEADING!r} 섹션이 없습니다.") from exc
    end = readme.find(README_SHOWCASE_END, start)
    if end == -1:
        end = len(readme)
    showcase = readme[start:end]
    records: list[dict[str, object]] = []
    seen: set[str] = set()

    for match in HTML_IMAGE_RE.finditer(showcase):
        attrs = {name.lower(): html.unescape(value) for name, value in HTML_ATTR_RE.findall(match.group(1))}
        path = attrs.get("src", "")
        if not LOCAL_IMAGE_RE.fullmatch(path) or path in seen:
            continue
        seen.add(path)
        absolute_offset = start + match.start()
        line = readme.count("\n", 0, absolute_offset) + 1
        records.append(
            {
                "image_path": path,
                "title": attrs.get("alt") or Path(path).stem,
                "offset": absolute_offset,
                "line": line,
            }
        )
    return showcase, records


def infer_readme_category(readme: str, offset: int, image_path: str) -> str:
    headings = list(re.finditer(r"<h2\b[^>]*>(.*?)</h2>", readme[:offset], re.IGNORECASE | re.DOTALL))
    if headings:
        label = strip_html(headings[-1].group(1))
        label = re.sub(r"^[^\w]+", "", label, flags=re.UNICODE).strip()
        if label:
            return label
    parent = PurePosixPath(image_path).parent.name.replace("-", " ")
    return parent.title() if parent else "README Showcase"


def infer_readme_details(readme: str, record: dict[str, object]) -> tuple[str, str, list[str], int]:
    offset = int(record["offset"])
    next_section = readme.find("<h2", offset + 1)
    if next_section == -1:
        next_section = readme.find(README_SHOWCASE_END, offset + 1)
    if next_section == -1:
        next_section = len(readme)
    region = readme[offset:next_section]

    sub_match = re.search(r"<sub>(.*?)</sub>", region, re.IGNORECASE | re.DOTALL)
    metadata = sub_match.group(1).strip() if sub_match else MISSING_METADATA
    prompt_match = PROMPT_RE.search(region)
    if prompt_match and PROMPT_RE.search(region, prompt_match.end()) is None:
        prompt = prompt_match.group(1)
        prompt_line = readme.count("\n", 0, offset + prompt_match.start(1)) + 1
    else:
        prompt = MISSING_PROMPT
        prompt_line = int(record["line"])
    return prompt, metadata, extract_urls(region), prompt_line


def parse_gallery(
    upstream: Path,
    upstream_url: str,
    commit: str,
    showcase_paths: set[str],
) -> tuple[list[dict[str, object]], set[str]]:
    references = upstream / "skills/gpt-image/references"
    gallery_files = sorted(path for path in references.glob("gallery-*.md") if path.name != "gallery.md")
    if not gallery_files:
        raise ValueError("gallery-*.md 정본 파일을 찾지 못했습니다.")

    entries: list[dict[str, object]] = []
    declared_paths: set[str] = set()
    for path in gallery_files:
        text = path.read_text(encoding="utf-8")
        matches = list(ENTRY_HEADING_RE.finditer(text))
        relative_source = path.relative_to(upstream).as_posix()
        for index, match in enumerate(matches):
            section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.end() : section_end]
            images = parse_declared_images(body)
            primary = choose_primary(images)
            if primary is None:
                raise ValueError(f"대표 이미지 경로가 없는 항목: {relative_source} No. {match.group(1)}")

            for image in images:
                safe_repo_path(image["image_path"])
                declared_paths.add(image["image_path"])

            image_path = primary["image_path"]
            image_id = PurePosixPath(image_path).stem
            metadata_match = METADATA_RE.search(body)
            metadata = metadata_match.group(1) if metadata_match else MISSING_METADATA
            prompt_match = PROMPT_RE.search(body)
            prompt = prompt_match.group(1) if prompt_match else MISSING_PROMPT
            category = metadata.split(" · ", 1)[0] if metadata_match else infer_readme_category(text, match.start(), image_path)
            heading_line = text.count("\n", 0, match.start()) + 1
            section_last_line = max(heading_line, text.count("\n", 0, section_end))
            evidence_url = source_url(
                upstream_url,
                commit,
                relative_source,
                heading_line,
                section_last_line,
            )
            section_paths = {image["image_path"] for image in images}
            entry = {
                "id": image_id,
                "gallery_number": int(match.group(1)),
                "title": strip_inline_markdown(match.group(2)),
                "category": category,
                "category_label": CATEGORY_LABELS.get(category, category),
                "image_path": image_path,
                "preview_path": "",
                "asset_path": "",
                "prompt": prompt,
                "prompt_status": "source" if prompt_match else "missing",
                "metadata": metadata,
                "source_urls": unique_urls([evidence_url], extract_urls(metadata)),
                "source_ref": f"{relative_source}#L{heading_line}-L{section_last_line}",
                "in_showcase": bool(section_paths & showcase_paths),
                "image_exists": (upstream / image_path).is_file(),
                "related_images": [
                    {
                        "image_path": image["image_path"],
                        "label": image["label"],
                        "kind": image["kind"],
                        "preview_path": "",
                        "asset_path": "",
                        "image_exists": (upstream / image["image_path"]).is_file(),
                        "in_showcase": image["image_path"] in showcase_paths,
                    }
                    for image in images
                    if image["image_path"] != image_path
                ],
            }
            entries.append(entry)

    return entries, declared_paths


def add_readme_only_entries(
    entries: list[dict[str, object]],
    declared_paths: set[str],
    records: list[dict[str, object]],
    readme: str,
    upstream: Path,
    upstream_url: str,
    commit: str,
) -> None:
    for record in records:
        image_path = str(record["image_path"])
        if image_path in declared_paths:
            continue
        safe_repo_path(image_path)
        prompt, metadata, external_urls, prompt_line = infer_readme_details(readme, record)
        line = int(record["line"])
        evidence_url = source_url(upstream_url, commit, "README.md", line, prompt_line)
        category = infer_readme_category(readme, int(record["offset"]), image_path)
        entries.append(
            {
                "id": PurePosixPath(image_path).stem,
                "gallery_number": None,
                "title": strip_inline_markdown(str(record["title"])),
                "category": category,
                "category_label": CATEGORY_LABELS.get(category, category),
                "image_path": image_path,
                "preview_path": "",
                "asset_path": "",
                "prompt": prompt,
                "prompt_status": "source" if prompt != MISSING_PROMPT else "missing",
                "metadata": metadata,
                "source_urls": unique_urls([evidence_url], external_urls),
                "source_ref": f"README.md#L{line}-L{prompt_line}",
                "in_showcase": True,
                "image_exists": (upstream / image_path).is_file(),
                "related_images": [],
            }
        )


def validate_entries(entries: list[dict[str, object]]) -> None:
    ids: set[str] = set()
    numbers: set[int] = set()
    for entry in entries:
        image_id = str(entry["id"])
        if image_id in ids:
            raise ValueError(f"중복 이미지 stem ID: {image_id}")
        ids.add(image_id)
        number = entry["gallery_number"]
        if number is not None:
            if int(number) in numbers:
                raise ValueError(f"중복 갤러리 번호: {number}")
            numbers.add(int(number))
    entries.sort(key=lambda item: (item["gallery_number"] is None, item["gallery_number"] or 0, item["id"]))


def load_pillow():
    try:
        from PIL import Image, ImageOps, features
    except ImportError:
        return None
    if not hasattr(Image, "Resampling") or not features.check("webp"):
        return None
    return Image, ImageOps


def copy_assets(upstream: Path, output: Path, entries: list[dict[str, object]]) -> str:
    assets_root = output / "assets"
    if assets_root.exists():
        shutil.rmtree(assets_root)
    original_root = assets_root / "original"
    preview_root = assets_root / "previews"
    pillow = load_pillow()
    cached: dict[str, tuple[str, str]] = {}

    def materialize(image_path: str, image_exists: bool) -> tuple[str, str]:
        if image_path in cached:
            return cached[image_path]
        relative = safe_repo_path(image_path)
        source = upstream.joinpath(*relative.parts)
        asset_relative = PurePosixPath("assets/original").joinpath(relative)
        asset_target = output.joinpath(*asset_relative.parts)
        if not image_exists:
            cached[image_path] = ("", "")
            return cached[image_path]

        source_resolved = source.resolve()
        upstream_resolved = upstream.resolve()
        if upstream_resolved not in source_resolved.parents:
            raise ValueError(f"원본 저장소 밖을 가리키는 이미지: {image_path}")
        asset_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, asset_target)
        preview_relative = asset_relative

        if pillow is not None:
            Image, ImageOps = pillow
            preview_relative = PurePosixPath("assets/previews").joinpath(relative).with_suffix(".webp")
            preview_target = output.joinpath(*preview_relative.parts)
            preview_target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with Image.open(source) as opened:
                    image = ImageOps.exif_transpose(opened)
                    image.thumbnail((720, 540), Image.Resampling.LANCZOS)
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                    image.save(preview_target, "WEBP", quality=82, method=6)
            except (OSError, ValueError):
                preview_relative = asset_relative
        cached[image_path] = (asset_relative.as_posix(), preview_relative.as_posix())
        return cached[image_path]

    for entry in entries:
        asset_path, preview_path = materialize(str(entry["image_path"]), bool(entry["image_exists"]))
        entry["asset_path"] = asset_path
        entry["preview_path"] = preview_path
        for related in entry["related_images"]:
            asset_path, preview_path = materialize(
                str(related["image_path"]), bool(related["image_exists"])
            )
            related["asset_path"] = asset_path
            related["preview_path"] = preview_path

    return "Pillow WebP thumbnails" if pillow is not None else "original images (Pillow unavailable)"


def catalog_json_for_html(catalog: dict[str, object]) -> str:
    value = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    return value.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>GPT Image 2 채택 카탈로그</title>
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
      --selected: #e2f1e9;
      --selected-line: #176747;
      --focus: #005fcc;
      --shadow: 0 10px 28px rgb(32 39 42 / 10%);
    }
    * { box-sizing: border-box; }
    html { background: var(--paper); scroll-behavior: auto; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgb(143 53 31 / 5%) 1px, transparent 1px) 0 0 / 28px 28px,
        var(--paper);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    button, input, select, textarea { font: inherit; }
    button, select, input[type="search"] {
      min-block-size: 44px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      color: var(--ink);
    }
    button { padding: 0.62rem 0.9rem; cursor: pointer; font-weight: 700; }
    button:hover { border-color: var(--accent); }
    button.primary { border-color: var(--accent); background: var(--accent); color: #fff; }
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
    .masthead { padding: clamp(2rem, 6vw, 5rem) max(1rem, calc((100vw - 1380px) / 2)); }
    .eyebrow {
      margin: 0 0 0.6rem;
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h1 { max-inline-size: 16ch; margin: 0; font-family: ui-serif, Georgia, serif; font-size: clamp(2.3rem, 7vw, 5.2rem); line-height: 0.98; letter-spacing: -0.035em; }
    .lede { max-inline-size: 66ch; margin: 1.25rem 0 0; font-size: clamp(1rem, 2vw, 1.2rem); }
    .notice { max-inline-size: 78ch; margin-block-start: 1.25rem; padding-inline-start: 1rem; border-inline-start: 4px solid var(--accent); color: var(--muted); }
    main { inline-size: min(1380px, calc(100% - 2rem)); margin-inline: auto; padding-block-end: 5rem; }
    .toolbar {
      display: grid;
      gap: 0.9rem;
      margin-block-end: 1.25rem;
      padding: 1rem;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgb(255 253 247 / 96%);
      box-shadow: var(--shadow);
    }
    .toolbar-grid { display: grid; grid-template-columns: minmax(15rem, 2fr) minmax(12rem, 1fr); gap: 0.75rem; }
    .field { display: grid; gap: 0.3rem; min-inline-size: 0; }
    .field > span, legend { color: var(--muted); font-size: 0.8rem; font-weight: 750; }
    input[type="search"], select { inline-size: 100%; padding-inline: 0.75rem; font-size: 1rem; }
    fieldset { min-inline-size: 0; margin: 0; padding: 0; border: 0; }
    .choice-row, .action-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem 1rem; }
    .choice {
      display: inline-flex;
      min-block-size: 44px;
      align-items: center;
      gap: 0.48rem;
      cursor: pointer;
    }
    .choice input { inline-size: 1.15rem; block-size: 1.15rem; accent-color: var(--accent); }
    .action-row { justify-content: space-between; }
    .status { margin: 0; color: var(--muted); font-variant-numeric: tabular-nums; }
    .storage-status { min-block-size: 1.5em; margin: 0; color: #7c2f1f; }
    .catalog-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 1fr)); gap: 1rem; align-items: start; }
    .card {
      min-inline-size: 0;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--surface);
      box-shadow: 0 4px 16px rgb(32 39 42 / 7%);
    }
    .card[data-selected="true"] { border: 2px solid var(--selected-line); background: var(--selected); }
    .image-link, .image-missing { display: grid; inline-size: 100%; aspect-ratio: 4 / 3; place-items: center; background: #e9e5db; }
    .image-link img { inline-size: 100%; block-size: 100%; object-fit: contain; }
    .image-missing { padding: 1rem; color: #7c2f1f; text-align: center; }
    .card-body { display: grid; gap: 0.85rem; padding: 1rem; }
    .badges { display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .badge { padding: 0.18rem 0.46rem; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); background: #fff; font-size: 0.72rem; font-weight: 750; }
    .badge.showcase { border-color: #a84528; color: #762811; background: var(--accent-soft); }
    .badge.selected { border-color: var(--selected-line); color: #0c5337; background: #fff; }
    .card h2 { margin: 0; font-family: ui-serif, Georgia, serif; font-size: 1.27rem; line-height: 1.25; overflow-wrap: anywhere; }
    .category { margin: 0; color: var(--accent); font-size: 0.84rem; font-weight: 800; }
    .metadata { margin: 0; color: var(--muted); font-size: 0.82rem; overflow-wrap: anywhere; }
    .select-label { display: flex; min-block-size: 44px; align-items: center; gap: 0.65rem; padding: 0.5rem 0.65rem; border-radius: 8px; background: rgb(255 255 255 / 72%); cursor: pointer; font-weight: 750; }
    .select-label input { flex: 0 0 auto; inline-size: 1.25rem; block-size: 1.25rem; accent-color: var(--selected-line); }
    details { border-block-start: 1px solid var(--line); padding-block-start: 0.65rem; }
    summary { min-block-size: 44px; padding-block: 0.55rem; cursor: pointer; font-weight: 750; }
    pre { max-block-size: 22rem; overflow: auto; margin: 0.5rem 0; padding: 0.8rem; border-radius: 8px; background: #1d292f; color: #f7f4ec; font: 0.78rem/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
    .source-list { margin: 0.7rem 0 0; padding-inline-start: 1.25rem; font-size: 0.82rem; }
    a { color: #71301e; text-underline-position: from-font; }
    .related { display: grid; gap: 0.55rem; }
    .related h3 { margin: 0; font-size: 0.86rem; }
    .related-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; }
    .related-item { min-inline-size: 0; }
    .related-item img { inline-size: 100%; aspect-ratio: 4 / 3; object-fit: contain; border: 1px solid var(--line); border-radius: 6px; background: #e9e5db; }
    .related-item span { display: block; color: var(--muted); font-size: 0.72rem; overflow-wrap: anywhere; }
    .notes-field textarea { inline-size: 100%; min-block-size: 5rem; resize: vertical; padding: 0.65rem; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); font-size: 1rem; }
    .empty { padding: 3rem 1rem; border: 1px dashed var(--line); border-radius: 12px; background: var(--surface); text-align: center; }
    [hidden] { display: none !important; }
    @media (min-width: 800px) {
      .toolbar { position: sticky; inset-block-start: 0.75rem; z-index: 10; }
      .toolbar { grid-template-columns: minmax(0, 1fr) auto; }
      .toolbar-grid { grid-column: 1 / -1; }
    }
    @media (max-width: 540px) {
      main { inline-size: min(100% - 1rem, 1380px); }
      .masthead { padding-inline: 1rem; }
      .toolbar-grid { grid-template-columns: 1fr; }
      .action-row { align-items: stretch; }
      .action-row button { inline-size: 100%; }
      h1 { font-size: clamp(2.25rem, 16vw, 3.7rem); }
    }
    @media (forced-colors: active) {
      .card[data-selected="true"] { border: 3px solid Highlight; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#catalog">카탈로그로 건너뛰기</a>
  <header class="masthead">
    <p class="eyebrow">GPT Image 2 · 선택 도구</p>
    <h1>보고, 비교하고, 직접 고르세요.</h1>
    <p class="lede">원본 README 쇼케이스와 전체 레퍼런스 갤러리를 한곳에서 비교해 채택할 항목을 선택하는 로컬 카탈로그입니다.</p>
    <p class="notice">선택과 메모는 이 브라우저의 로컬 저장소에만 보관됩니다. 이 페이지는 이미지 생성 API를 호출하거나 데이터를 외부로 전송하지 않습니다. <strong>Curated</strong>는 원본 저장소의 표기이며, 원본 저장소의 MIT 라이선스가 모든 외부 입력의 권리를 증명하지는 않습니다. 외부 저자와 출처의 이용 조건을 별도로 확인하세요.</p>
  </header>

  <main id="catalog" tabindex="-1">
    <section class="toolbar" aria-label="카탈로그 필터와 선택 내보내기">
      <div class="toolbar-grid">
        <label class="field" for="search">
          <span>검색</span>
          <input id="search" type="search" placeholder="제목, 카테고리, 프롬프트 검색" autocomplete="off">
        </label>
        <label class="field" for="category">
          <span>카테고리</span>
          <select id="category"><option value="">모든 카테고리</option></select>
        </label>
      </div>
      <fieldset>
        <legend>표시 범위</legend>
        <div class="choice-row">
          <label class="choice"><input type="radio" name="view" value="showcase" checked> README 쇼케이스</label>
          <label class="choice"><input type="radio" name="view" value="all"> 전체 갤러리</label>
          <label class="choice"><input id="selected-only" type="checkbox"> 선택한 항목만</label>
        </div>
      </fieldset>
      <div class="action-row">
        <p id="status" class="status" role="status" aria-live="polite"></p>
        <div class="choice-row">
          <button id="clear" type="button">선택 비우기</button>
          <button id="export" type="button" class="primary">선택 JSON 내보내기</button>
        </div>
      </div>
      <p id="storage-status" class="storage-status" role="status" aria-live="polite"></p>
    </section>

    <div id="grid" class="catalog-grid"></div>
    <p id="empty" class="empty" hidden>현재 검색과 필터에 맞는 항목이 없습니다. 검색어 또는 필터를 바꿔 보세요.</p>
  </main>

  <script id="catalog-data" type="application/json">__CATALOG_JSON__</script>
  <script>
    (() => {
      "use strict";
      const catalog = JSON.parse(document.getElementById("catalog-data").textContent);
      const storageKey = `gpt-image-catalog-selection-v1:${catalog.upstream_commit}`;
      const grid = document.getElementById("grid");
      const search = document.getElementById("search");
      const category = document.getElementById("category");
      const selectedOnly = document.getElementById("selected-only");
      const status = document.getElementById("status");
      const storageStatus = document.getElementById("storage-status");
      const empty = document.getElementById("empty");
      const cards = new Map();
      let selected = new Set();
      let notes = {};

      function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
      }

      function displayMetadata(value) {
        return value
          .replace(/`/g, "")
          .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
          .replace(/<[^>]+>/g, " ")
          .replace(/\s+/g, " ")
          .trim();
      }

      function sourceLabel(url, index) {
        if (index === 0) return "고정된 원본 항목";
        try {
          const parsed = new URL(url);
          return `외부 출처 · ${parsed.hostname}`;
        } catch (_) {
          return `출처 ${index + 1}`;
        }
      }

      function persist() {
        try {
          localStorage.setItem(storageKey, JSON.stringify({
            schema_version: 1,
            selected_ids: [...selected],
            notes,
          }));
          storageStatus.textContent = "";
        } catch (_) {
          storageStatus.textContent = "선택을 브라우저에 저장하지 못했습니다. 현재 탭에서는 계속 선택할 수 있습니다.";
        }
      }

      function restore() {
        try {
          const raw = localStorage.getItem(storageKey);
          if (!raw) return;
          const saved = JSON.parse(raw);
          const validIds = new Set(catalog.entries.map((entry) => entry.id));
          selected = new Set((saved.selected_ids || []).filter((id) => validIds.has(id)));
          notes = saved.notes && typeof saved.notes === "object" ? saved.notes : {};
        } catch (_) {
          storageStatus.textContent = "저장된 선택을 읽지 못했습니다. 새 선택은 현재 탭에서 사용할 수 있습니다.";
        }
      }

      function makeImage(entry, className) {
        if (!entry.image_exists || !entry.preview_path || !entry.asset_path) {
          return element("div", "image-missing", `이미지 파일 없음 · ${entry.image_path}`);
        }
        const link = element("a", className || "image-link");
        link.href = entry.asset_path;
        link.target = "_blank";
        link.rel = "noopener";
        link.setAttribute("aria-label", `${entry.title || entry.label} 원본 이미지 확대`);
        const image = document.createElement("img");
        image.src = entry.preview_path;
        image.alt = entry.title || entry.label || "관련 이미지";
        image.loading = "lazy";
        image.decoding = "async";
        link.append(image);
        return link;
      }

      function buildRelated(entry) {
        if (!entry.related_images.length) return null;
        const section = element("section", "related");
        section.append(element("h3", "", "관련 이미지"));
        const relatedGrid = element("div", "related-grid");
        for (const related of entry.related_images) {
          const item = element("div", "related-item");
          if (related.image_exists && related.preview_path && related.asset_path) {
            const link = element("a");
            link.href = related.asset_path;
            link.target = "_blank";
            link.rel = "noopener";
            link.setAttribute("aria-label", `${related.label} 원본 이미지 확대`);
            const image = document.createElement("img");
            image.src = related.preview_path;
            image.alt = related.label;
            image.loading = "lazy";
            image.decoding = "async";
            link.append(image);
            item.append(link);
          } else {
            item.append(element("span", "", `이미지 파일 없음 · ${related.image_path}`));
          }
          item.append(element("span", "", related.label));
          relatedGrid.append(item);
        }
        section.append(relatedGrid);
        return section;
      }

      function buildCard(entry) {
        const card = element("article", "card");
        card.dataset.id = entry.id;
        card.dataset.showcase = String(entry.in_showcase);
        card.dataset.category = entry.category;
        card.dataset.search = [entry.title, entry.category, entry.category_label, entry.metadata, entry.prompt]
          .join(" ").toLocaleLowerCase("ko");

        const imageData = { ...entry, title: entry.title };
        card.append(makeImage(imageData));
        const body = element("div", "card-body");
        const badges = element("div", "badges");
        badges.append(element("span", "badge", entry.gallery_number === null ? "README" : `No. ${entry.gallery_number}`));
        if (entry.in_showcase) badges.append(element("span", "badge showcase", "쇼케이스"));
        if (!entry.image_exists) badges.append(element("span", "badge", "이미지 누락"));
        const selectedBadge = element("span", "badge selected", "선택됨");
        selectedBadge.hidden = true;
        badges.append(selectedBadge);
        body.append(badges);
        body.append(element("p", "category", entry.category_label));
        body.append(element("h2", "", entry.title));
        body.append(element("p", "metadata", displayMetadata(entry.metadata)));

        const selectLabel = element("label", "select-label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = selected.has(entry.id);
        checkbox.setAttribute("aria-label", `${entry.title} 채택 후보로 선택`);
        selectLabel.append(checkbox, document.createTextNode("채택 후보로 선택"));
        body.append(selectLabel);

        const related = buildRelated(entry);
        if (related) body.append(related);

        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = entry.prompt_status === "missing" ? "원문 확인 · 프롬프트 누락" : "원문과 출처 보기";
        details.append(summary);
        details.append(element("pre", "", entry.prompt || "원본에서 대응 프롬프트를 확정하지 못했습니다."));
        const sources = element("ul", "source-list");
        entry.source_urls.forEach((url, index) => {
          const item = document.createElement("li");
          const link = element("a", "", sourceLabel(url, index));
          link.href = url;
          link.target = "_blank";
          link.rel = "noopener";
          item.append(link);
          sources.append(item);
        });
        details.append(sources);
        body.append(details);

        const notesField = element("label", "field notes-field");
        notesField.hidden = !checkbox.checked;
        notesField.append(element("span", "", "선택 메모"));
        const textarea = document.createElement("textarea");
        textarea.value = typeof notes[entry.id] === "string" ? notes[entry.id] : "";
        textarea.placeholder = "채택 이유, 수정 방향, 주의점";
        textarea.setAttribute("aria-label", `${entry.title} 선택 메모`);
        notesField.append(textarea);
        body.append(notesField);

        function updateSelectedState() {
          card.dataset.selected = String(checkbox.checked);
          selectedBadge.hidden = !checkbox.checked;
          notesField.hidden = !checkbox.checked;
        }
        updateSelectedState();

        checkbox.addEventListener("change", () => {
          if (checkbox.checked) selected.add(entry.id);
          else selected.delete(entry.id);
          updateSelectedState();
          persist();
          applyFilters();
        });
        textarea.addEventListener("input", () => {
          notes[entry.id] = textarea.value;
          persist();
        });

        card.append(body);
        cards.set(entry.id, { card, checkbox, selectedBadge, notesField, textarea, entry });
        return card;
      }

      function applyFilters() {
        const query = search.value.trim().toLocaleLowerCase("ko");
        const categoryValue = category.value;
        const view = document.querySelector('input[name="view"]:checked').value;
        let visible = 0;
        for (const { card, entry } of cards.values()) {
          const matches = (!query || card.dataset.search.includes(query))
            && (!categoryValue || entry.category === categoryValue)
            && (view === "all" || entry.in_showcase)
            && (!selectedOnly.checked || selected.has(entry.id));
          card.hidden = !matches;
          if (matches) visible += 1;
        }
        status.textContent = `표시 ${visible.toLocaleString("ko-KR")}개 · 선택 ${selected.size.toLocaleString("ko-KR")}개 · 전체 ${catalog.entries.length.toLocaleString("ko-KR")}개`;
        empty.hidden = visible !== 0;
      }

      function exportSelection() {
        const selectedIds = catalog.entries.map((entry) => entry.id).filter((id) => selected.has(id));
        const selectedNotes = Object.fromEntries(selectedIds.map((id) => [id, typeof notes[id] === "string" ? notes[id] : ""]));
        const payload = {
          schema_version: 1,
          upstream_commit: catalog.upstream_commit,
          selected_ids: selectedIds,
          notes: selectedNotes,
        };
        const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "gpt-image-catalog-selection.json";
        document.body.append(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        storageStatus.textContent = `선택 ${selectedIds.length.toLocaleString("ko-KR")}개를 JSON으로 내보냈습니다.`;
      }

      restore();
      const categories = [];
      const seenCategories = new Set();
      for (const entry of catalog.entries) {
        if (!seenCategories.has(entry.category)) {
          seenCategories.add(entry.category);
          categories.push([entry.category, entry.category_label]);
        }
        grid.append(buildCard(entry));
      }
      for (const [value, label] of categories) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        category.append(option);
      }

      search.addEventListener("input", applyFilters);
      category.addEventListener("change", applyFilters);
      selectedOnly.addEventListener("change", applyFilters);
      document.querySelectorAll('input[name="view"]').forEach((input) => input.addEventListener("change", applyFilters));
      document.getElementById("export").addEventListener("click", exportSelection);
      document.getElementById("clear").addEventListener("click", () => {
        selected.clear();
        for (const item of cards.values()) {
          item.checkbox.checked = false;
          item.card.dataset.selected = "false";
          item.selectedBadge.hidden = true;
          item.notesField.hidden = true;
        }
        persist();
        applyFilters();
        storageStatus.textContent = "선택을 비웠습니다. 메모는 다시 선택하면 복원됩니다.";
      });
      applyFilters();
    })();
  </script>
</body>
</html>
'''


def build(upstream: Path, output: Path) -> dict[str, object]:
    upstream = upstream.resolve()
    output = output.resolve()
    readme_path = upstream / "README.md"
    if not readme_path.is_file():
        raise ValueError(f"원본 README를 찾지 못했습니다: {readme_path}")

    upstream_url = normalize_remote(run_git(upstream, "remote", "get-url", "origin"))
    commit = run_git(upstream, "rev-parse", "HEAD")
    readme = readme_path.read_text(encoding="utf-8")
    _, showcase_records = parse_showcase(readme)
    showcase_paths = {str(record["image_path"]) for record in showcase_records}
    entries, declared_paths = parse_gallery(upstream, upstream_url, commit, showcase_paths)
    add_readme_only_entries(
        entries,
        declared_paths,
        showcase_records,
        readme,
        upstream,
        upstream_url,
        commit,
    )
    validate_entries(entries)

    output.mkdir(parents=True, exist_ok=True)
    preview_mode = copy_assets(upstream, output, entries)
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "upstream_url": upstream_url,
        "upstream_commit": commit,
        "entries": entries,
    }
    (output / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "index.html").write_text(
        HTML_TEMPLATE.replace("__CATALOG_JSON__", catalog_json_for_html(catalog)),
        encoding="utf-8",
    )
    print(
        f"Built {len(entries)} entries ({sum(bool(entry['in_showcase']) for entry in entries)} showcase) "
        f"at {output} using {preview_mode}."
    )
    return catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static Korean selection catalog from a GPT Image 2 Skill clone."
    )
    parser.add_argument("--upstream", required=True, type=Path, help="GPT Image 2 Skill clone")
    parser.add_argument("--output", required=True, type=Path, help="output directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build(args.upstream, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
