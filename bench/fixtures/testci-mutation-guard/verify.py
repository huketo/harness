#!/usr/bin/env python3
"""Grades the test suite under tests/ with a mutation guard.

The run passes only when all three conditions hold:

  1. at least one tests/**/*.test.ts file exists,
  2. `bun test` passes against the original src/money.ts, reporting at least
     one executed test and no failure,
  3. against each mutant of src/money.ts under mutations/, the same suite
     reports at least one failed test.

A mutant counts as detected only when the JUnit report lists a failing test.
A crashed run, a suite that never loaded, and a process that exits on its own
leave no failing test behind and therefore detect nothing.

Every command runs inside a throwaway copy of this project under a random
name, so the working tree is never modified and the copy carries no hint of
which module it holds. The graded sources are pinned by salted digests, so a
run that rewrites src/money.ts or one of the mutants is rejected instead of
graded.
"""

from __future__ import annotations

import hashlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = "src/money.ts"
TEST_TIMEOUT_SECONDS = 120
SALT = b"hbench/testci-mutation-guard/v3"
PINNED_DIGESTS = {
    "src/money.ts": "99631449046f9b0ac6ce7874a5fd5f671d3e1734f456c7e034c8c4cdc71ff53e",
    "mutations/convert-unrounded.ts": "ed667deb36d894e01903c18cee204805b69bd1edb97fbd9b301d5829985d1ace",
    "mutations/currency-decimals.ts": "df50e7e313921d3c1295fc9e368b54e9a4f96d33be763312b1755139ad60cddd",
    "mutations/negative-sign.ts": "eaa6cb240005d897260d3e7edd972378472cb58a4f2757ed945ac8fb1341737f",
    "mutations/rate-inverse.ts": "a6fe349302ca84f14b6aa12457d9cfc3b413e6860d7052fcf155be51d8f2f020",
    "mutations/rounding-mode.ts": "09f983d5f057ea8f7f2ae3c0dcbf9901325ee1057600131bac5410ab2fa6d593",
    "mutations/sum-mixed-currency.ts": "1f28215d598723a52bc1f26aadbb9ea0cf0c7b01dcb228c86b815f40ecdf6da5",
    "mutations/unknown-currency-default.ts": "cdf0ee778130c34750a5c4a4aec0e2e2b17b362599fa8d7f2e2c3920fcfd2523",
}
MUTATIONS = tuple(sorted(name for name in PINNED_DIGESTS if name != SOURCE))
COPY_EXCLUDES = shutil.ignore_patterns("node_modules", ".git", "mutations", "verify.py")


@dataclass(frozen=True)
class SuiteResult:
    exit_code: int
    tests: int
    failures: int
    reported: bool
    output: str


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_pinned_sources() -> None:
    for relative, expected in PINNED_DIGESTS.items():
        path = ROOT / relative
        if not path.is_file():
            fail(f"{relative} is missing")
        actual = hashlib.sha256(SALT + path.read_bytes()).hexdigest()
        if actual != expected:
            fail(f"{relative} was modified; it is graded material and must stay as delivered")


def read_report(report: Path) -> tuple[bool, int, int]:
    if not report.is_file():
        return False, 0, 0
    try:
        root = ElementTree.parse(report).getroot()
    except ElementTree.ParseError:
        return False, 0, 0
    tests = int(root.get("tests", "0"))
    failures = int(root.get("failures", "0"))
    return True, tests, failures


def run_suite(replacement: Path | None) -> SuiteResult:
    with tempfile.TemporaryDirectory() as workspace:
        root = Path(workspace)
        project = root / secrets.token_hex(6)
        shutil.copytree(ROOT, project, ignore=COPY_EXCLUDES)
        if replacement is not None:
            shutil.copyfile(replacement, project / SOURCE)
        report = root / f"{secrets.token_hex(6)}.xml"
        completed = subprocess.run(
            ["bun", "test", "--reporter=junit", "--reporter-outfile", str(report)],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
        reported, tests, failures = read_report(report)
    return SuiteResult(
        exit_code=completed.returncode,
        tests=tests,
        failures=failures,
        reported=reported,
        output=(completed.stdout[-4000:] + completed.stderr[-4000:]),
    )


def main() -> int:
    check_pinned_sources()

    tests_dir = ROOT / "tests"
    test_files = sorted(path for path in tests_dir.rglob("*.test.ts") if path.is_file()) if tests_dir.is_dir() else []
    if not test_files:
        fail("no tests/**/*.test.ts file exists")
    print(f"found {len(test_files)} test file(s): {', '.join(str(p.relative_to(ROOT)) for p in test_files)}")

    baseline = run_suite(None)
    if not baseline.reported:
        print(baseline.output)
        fail("the suite produced no JUnit report against the original module; it did not run to completion")
    if baseline.exit_code != 0 or baseline.failures != 0:
        print(baseline.output)
        fail(f"the suite does not pass against the original module ({baseline.failures} failing test(s))")
    if baseline.tests < 1:
        fail("the suite executed no test against the original module")
    print(f"the original module passes {baseline.tests} test(s)")

    survivors: list[str] = []
    for mutation in MUTATIONS:
        result = run_suite(ROOT / mutation)
        if result.failures >= 1:
            print(f"detected: {mutation} ({result.failures} failing test(s))")
            continue
        survivors.append(mutation)
        reason = "no test failed" if result.reported else "the suite did not run to completion"
        print(f"undetected: {mutation} ({reason})")

    if survivors:
        fail(
            "these mutants are not detected by a failing test: "
            + ", ".join(survivors)
            + f"; all {len(MUTATIONS)} mutants must make at least one test fail"
        )
    print(f"all {len(MUTATIONS)} mutants are detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
