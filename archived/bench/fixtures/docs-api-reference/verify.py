"""Grade docs/API.md against the source tree it documents.

The truth comes from the protected sources, not from this file: `src/*.ts` is
parsed for the declarations of every re-exported symbol, the public members of
every exported class and interface, and the constant values, and the document
is then measured against those declarations. `facts.json` only names what has
to be documented; the expected text is derived from the source every run, so a
source change moves the target with it.

Four checks: the document exists and is at least 80 lines, every export has a
`## <name>` section whose ```ts block carries the declarations that export
really has, every entry in facts.json has its source-derived value in the
document, and no identifier this release removed appears. Prose quality is not
graded.

The removed identifiers are stored as salted SHA-256 digests, not plaintext, so
reading this file does not hand over the answer. CHANGELOG.md already says what
was removed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DOC = Path("docs/API.md")
SOURCE_DIR = Path("src")
INDEX = SOURCE_DIR / "index.ts"
FACTS = Path("facts.json")

MINIMUM_LINES = 80

REMOVED_SALT = "docs-api-reference/removed/v1"
REMOVED_DIGESTS = {
    "fc9ee743f89a7d3b91a567ea8acd288aaf9b2dd4fe42ec6834221c64bf8d6dba",
    "062ac2d9edb7e9b3e8401484779deaf5d51025a65498b4a2f197643044cdc0a5",
}

# Each fact names a symbol in the sources; the expected text is whatever the
# sources currently declare for it. `declaration` is a top-level export,
# `member` is `<Class>.<member>`, and `constant-values` names module-private
# constants whose values have to appear in the document.
FACT_RULES: dict[str, tuple[str, str]] = {
    "factory-signature": ("declaration", "createFeedClient"),
    "get-record-signature": ("member", "FeedClient.getRecord"),
    "retry-signature": ("declaration", "retryWithBackoff"),
    "cache-set-signature": ("member", "MemoryCache.set"),
    "error-code-field": ("member", "FeedError.code"),
    "timeout-error-parent": ("declaration", "FeedTimeoutError"),
    "decode-error-parent": ("declaration", "FeedDecodeError"),
    "closed-error-parent": ("declaration", "FeedClosedError"),
    "default-cache-ttl": ("declaration", "DEFAULT_CACHE_TTL_MS"),
    "default-cache-capacity": ("declaration", "DEFAULT_CACHE_CAPACITY"),
    "default-retry-attempts": ("declaration", "DEFAULT_RETRY_ATTEMPTS"),
    "backoff-schedule": ("constant-values", "BASE_DELAY_MS,MAX_DELAY_MS"),
}

MODIFIERS = ("readonly", "static", "override", "public")

failures: list[str] = []


@dataclass
class Symbol:
    """One top-level declaration and the members it publishes."""

    name: str
    kind: str
    signature: str
    members: dict[str, str] = field(default_factory=dict)


def squeeze(text: str) -> str:
    """Comparison form: no whitespace, no table escapes, no cosmetic tokens.

    Both the source declaration and the document go through this, so
    formatting, `export`/`async` keywords, an optional-marker written as `?:`,
    a trailing comma before `)`, and digit grouping cannot make a faithful
    document fail.
    """
    text = text.replace("\\|", "|")
    text = re.sub(r"\s+", "", text)
    text = text.replace("export", "").replace("async", "")
    text = text.replace("?:", ":").replace(",)", ")").replace(";", "")
    return re.sub(r"(?<=\d)[,_](?=\d)", "", text)


def strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


def collect(lines: list[str], start: int) -> tuple[str, int]:
    """Join one declaration, which may wrap across lines, into a single line."""
    depth = 0
    parts: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        parts.append(line.strip())
        depth += line.count("(") - line.count(")")
        index += 1
        if depth <= 0 and ("{" in line or line.rstrip().endswith(";")):
            break
    return " ".join(part for part in parts if part), index


def skip_block(lines: list[str], start: int) -> int:
    """Advance past a body whose opening brace was already consumed."""
    depth = 1
    index = start
    while index < len(lines) and depth > 0:
        depth += lines[index].count("{") - lines[index].count("}")
        index += 1
    return index


def as_signature(text: str) -> str:
    body = text.rindex("{") if text.rstrip().endswith("{") else None
    signature = text[:body] if body is not None else text
    signature = signature.strip().rstrip(";").strip()
    return re.sub(r"^export\s+", "", signature)


def member_name(signature: str) -> str | None:
    rest = signature
    while True:
        head = rest.split(" ", 1)[0]
        if head in MODIFIERS or head in ("get", "set", "async"):
            rest = rest.split(" ", 1)[1] if " " in rest else ""
            continue
        break
    found = re.match(r"([A-Za-z_]\w*)", rest)
    return found.group(1) if found else None


def parse_body(lines: list[str], start: int) -> tuple[dict[str, str], int]:
    """Public members declared directly inside a class or interface body."""
    members: dict[str, str] = {}
    index = start
    while index < len(lines):
        line = lines[index]
        if line.startswith("}"):
            return members, index + 1
        if not line.strip() or len(line) - len(line.lstrip()) != 2:
            index += 1
            continue
        private = re.match(r"(private|protected)\b", line.strip()) or line.strip().startswith("#")
        text, index = collect(lines, index)
        if text.rstrip().endswith("{"):
            index = skip_block(lines, index)
        if private:
            continue
        signature = as_signature(text)
        name = member_name(signature)
        if name is not None:
            members[name] = signature
    return members, index


def parse_source(source: str) -> tuple[dict[str, Symbol], dict[str, str]]:
    symbols: dict[str, Symbol] = {}
    constants: dict[str, str] = {}
    lines = strip_comments(source).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line[0].isspace():
            index += 1
            continue
        head = re.sub(r"^export\s+", "", line.strip())
        if head.startswith(("class ", "interface ")):
            text, index = collect(lines, index)
            signature = as_signature(text)
            members, index = parse_body(lines, index)
            name = signature.split()[1]
            symbols[name] = Symbol(name, signature.split()[0], signature, members)
            continue
        if re.match(r"(?:async\s+)?function\s", head):
            text, index = collect(lines, index)
            signature = as_signature(text)
            name = re.search(r"function\s+([A-Za-z_]\w*)", signature).group(1)
            symbols[name] = Symbol(name, "function", signature)
            index = skip_block(lines, index)
            continue
        if head.startswith("const "):
            text, index = collect(lines, index)
            signature = as_signature(text)
            name = re.search(r"const\s+([A-Za-z_]\w*)", signature).group(1)
            constants[name] = signature.split("=", 1)[1].strip()
            symbols[name] = Symbol(name, "const", signature)
            continue
        index += 1
    return symbols, constants


def public_exports(source: str) -> list[str]:
    """Names re-exported from src/index.ts, in declaration order."""
    names: list[str] = []
    for block in re.findall(r"export\s+(?:type\s+)?\{([^}]*)\}", source):
        names.extend(name.strip() for name in block.split(",") if name.strip())
    return names


def sections(document: str) -> dict[str, str]:
    """`## ` sections keyed by the bare identifier the heading names."""
    found: dict[str, str] = {}
    matches = list(re.finditer(r"^##[ \t]+(.+?)[ \t]*$", document, flags=re.MULTILINE))
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(document)
        title = match.group(1).strip().strip("`").strip()
        if title.endswith("()"):
            title = title[:-2].strip()
        found[title] = document[match.end() : end]
    return found


def code_blocks(section: str) -> str:
    return "\n".join(re.findall(r"```(?:ts|typescript)?\n(.*?)```", section, flags=re.DOTALL))


if not DOC.is_file():
    print(f"{DOC} does not exist", file=sys.stderr)
    raise SystemExit(1)

document = DOC.read_text(encoding="utf-8")
line_count = len(document.splitlines())
if line_count < MINIMUM_LINES:
    failures.append(f"{DOC} has {line_count} lines, fewer than the required {MINIMUM_LINES}")

symbols: dict[str, Symbol] = {}
constants: dict[str, str] = {}
for path in sorted(SOURCE_DIR.glob("*.ts")):
    if path == INDEX:
        continue
    file_symbols, file_constants = parse_source(path.read_text(encoding="utf-8"))
    symbols.update(file_symbols)
    constants.update(file_constants)

exports = public_exports(INDEX.read_text(encoding="utf-8"))
documented = sections(document)
for name in exports:
    symbol = symbols[name]
    section = documented.get(name)
    if section is None:
        failures.append(f"{DOC} has no '## {name}' section")
        continue
    declared = squeeze(code_blocks(section))
    if not declared:
        failures.append(f"the '## {name}' section of {DOC} has no ```ts code block")
        continue
    missing = [
        signature
        for signature in [symbol.signature, *symbol.members.values()]
        if squeeze(signature) not in declared
    ]
    if missing:
        failures.append(
            f"the '## {name}' section of {DOC} does not carry {len(missing)} declaration(s) "
            f"that src/ publishes: {', '.join(member_name(signature) or name for signature in missing)}"
        )

whole = squeeze(document)
facts = json.loads(FACTS.read_text(encoding="utf-8"))["facts"]
missing_facts: list[str] = []
for fact in facts:
    kind, target = FACT_RULES[fact["id"]]
    if kind == "declaration":
        expected = [symbols[target].signature]
    elif kind == "member":
        owner, member = target.split(".")
        expected = [symbols[owner].members[member]]
    else:
        expected = [constants[name] for name in target.split(",")]
    if any(squeeze(value) not in whole for value in expected):
        missing_facts.append(fact["id"])
if missing_facts:
    failures.append(f"required facts missing from {DOC}: {', '.join(missing_facts)}")

stale = sorted(
    name
    for name in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", document))
    if hashlib.sha256((REMOVED_SALT + name).encode("utf-8")).hexdigest() in REMOVED_DIGESTS
)
if stale:
    failures.append(f"{DOC} documents identifiers that this release removed: {', '.join(stale)}")

if failures:
    for failure in failures:
        print(failure, file=sys.stderr)
    raise SystemExit(1)

print(
    f"{DOC}: {line_count} lines, {len(exports)} exports with matching declarations, "
    f"{len(facts)} facts present"
)
