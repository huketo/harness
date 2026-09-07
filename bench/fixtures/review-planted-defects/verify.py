"""Grade answers/findings.txt for the planted-defect review task.

The expected findings are stored as salted SHA-256 digests only. Reading this
file does not reveal which file, line, or code is expected. Each expected
finding can be hit at most once, so repeating one correct claim does not lift
recall.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

SALT = "hbench:review-planted-defects:2026-09:v1"
LINE_TOLERANCE = 2
TOTAL_DEFECTS = 6
REQUIRED_HITS = 5
MIN_PRECISION = 0.7

EXPECTED_DIGESTS = frozenset(
    (
        "2c129e6bbbadf3c0ab085973494608e6c7e5af15254d11af805c12affe835c75",
        "63697c8f0952d823f9c932bffa8eb9a1268f9dac7adeaabf144d718f40f2212c",
        "7dfba73c4400ed50c79e2d8af1620ec8680553ec4c96e5a59311b1d27d1a3018",
        "982694337a0897001c2ac8eff00e43690653c92a236ade0861c3b91fa990a29a",
        "c0902d8a1ab5d002b4d0dcdf6b723a0a0db3d552aef8f294bd2dc73fc496f37f",
        "d58b422b4582d7a528cf39307495c2c6486204103c96af3fa70722312eb552c5",
    )
)

ALLOWED_CODES = frozenset(
    (
        "CONVENTION",
        "MISSING_CLEANUP",
        "OFF_BY_ONE",
        "RACE",
        "UNHANDLED_REJECTION",
        "WRONG_ERROR_TYPE",
    )
)

ANSWER = Path("answers/findings.txt")
CLAIM_PREFIX = "FINDING="
FINDING = re.compile(r"^FINDING=(?P<path>[^:]+):(?P<line>\d+):(?P<code>[A-Za-z_]+)$")
OFFSETS = (0, -1, 1, -2, 2)


def normalize_path(raw: str) -> str:
    text = raw.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if text.startswith("a/") or text.startswith("b/"):
        text = text[2:]
    return text.lstrip("/")


def parse_claim(raw: str) -> tuple[str, int, str] | None:
    match = FINDING.match(raw)
    if match is None:
        return None
    path = normalize_path(match.group("path"))
    line = int(match.group("line"))
    code = match.group("code")
    if not path or line < 1 or code not in ALLOWED_CODES:
        return None
    return (path, line, code)


def main() -> int:
    if not ANSWER.is_file():
        print("answers/findings.txt does not exist", file=sys.stderr)
        return 1
    claims = [line.strip() for line in ANSWER.read_text(encoding="utf-8").splitlines()]
    claims = [line for line in claims if line.startswith(CLAIM_PREFIX)]
    if not claims:
        print("answers/findings.txt has no FINDING=<path>:<line>:<code> line", file=sys.stderr)
        return 1
    parsed = [parse_claim(claim) for claim in claims]
    malformed = sum(1 for finding in parsed if finding is None)
    remaining = set(EXPECTED_DIGESTS)
    hits = 0
    for finding in parsed:
        if finding is None:
            continue
        path, line, code = finding
        for offset in OFFSETS:
            candidate = hashlib.sha256(
                f"{SALT}|{path}|{line + offset}|{code}".encode("utf-8")
            ).hexdigest()
            if candidate in remaining:
                remaining.discard(candidate)
                hits += 1
                break
    recall = hits / TOTAL_DEFECTS
    precision = hits / len(claims)
    print(
        f"claims={len(claims)} malformed={malformed} hits={hits}/{TOTAL_DEFECTS} "
        f"recall={recall:.3f} precision={precision:.3f}"
    )
    if malformed:
        print(
            f"{malformed} claim(s) do not match FINDING=<path>:<line>:<code> with a code from codes.md",
            file=sys.stderr,
        )
    failed = False
    if hits < REQUIRED_HITS:
        print(f"recall below {REQUIRED_HITS}/{TOTAL_DEFECTS}", file=sys.stderr)
        failed = True
    if precision < MIN_PRECISION:
        print(f"precision below {MIN_PRECISION}", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
