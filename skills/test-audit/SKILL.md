---
name: test-audit
description: Audit or prune existing tests for low value, duplication, implementation coupling, or the test-only production seams they keep alive.
---

# Test Audit

Remove tests that cost more than the confidence they buy, and the production seams that exist only for them. The measure is confidence retained, not deletion count: a sweep that deletes one test and retires its seam beats one that deletes twenty uncertain candidates.

The target project owns its runner, gates, commit flow and publication rules. This skill owns the judgment. For authoring a new test, the `tdd` skill owns the procedure; [patterns.md](patterns.md) is the shared junk checklist both skills apply. To prune one component's whole test surface in a single change, read [CAMPAIGN.md](CAMPAIGN.md) before step 1.

## 1. Scope and baseline

Name the directories, packages or suites in scope. Read the project's agent instructions, contribution guide, CI configuration and package or build manifests to find the real test runner, the file discovery rules and the gates a change must pass. Take commands from those sources; when none exist, report the missing prerequisite instead of guessing one.

Exclude test-shaped data: benchmark or task fixtures, grading oracles, intentionally failing sample tests, generated or vendored suites, golden files a generator owns, and model-evaluation datasets. Deleting or "repairing" them breaks the tool that consumes them.

Run the in-scope tests once at a pinned revision and record each file's result. Keep baseline failures in their own list; a failing test may be a product bug, not a stale test.

**Done:** every in-scope file has a recorded baseline result, or its missing prerequisite is recorded.

## 2. Read-only discovery

Hunt for the [junk patterns](patterns.md) without editing. For a broad scope, split lanes along production owner boundaries (not file prefixes) and give each lane to a read-only subagent when available. Prefer a few high-confidence candidates over a speculative inventory.

**Done:** a candidate list where each entry names the pattern it matches.

## 3. Judge each candidate

Read the complete test and its production owner: the entry point, callers, callees, sibling implementations, overlapping tests, CI routing and relevant history. When a test claims dependency-backed behavior, read the dependency's source or types. Judge a test by its assertions, not its name.

### Retention bar

Keep a test when it independently enforces a public API, SDK, protocol, configuration, migration, storage, security, platform, default, prompt-byte, generated cross-language, package, release or architecture contract. Also keep:

- call ordering when the order is observable behavior;
- a regression with a credible failure mode;
- source inspection when it is the cheapest independent guard: it fails when the contract changes (the user-facing key, byte or path) and survives an identifier-only refactor;
- a retained test that fails on the baseline: reproduce it, repair the owner in its own commit, and prove the repair with a control run that reverts it and shows the old failure.

Static or slow is not a deletion reason. A test that must change under a behavior-preserving refactor is suspect, not automatically deletable: when it happens to cover a real contract, rewrite it at the owning boundary; delete it only once the evidence below shows no independent contract.

### Candidate evidence

Record every field before editing. A missing field means the candidate is not ready:

- exact test name and location;
- what failure it can actually detect;
- non-test callers of the covered production or support seam;
- the stronger remaining owner-boundary proof, or why no contract exists;
- relevant history and the reason the test or seam exists;
- the production or test-support code its removal unlocks;
- copies of the same test elsewhere (another repository, branch or vendored tree) and who owns updating them;
- risk and the focused validation command.

**Done:** every candidate is marked retain, repair, consolidate (naming the absorbing test) or delete, with its evidence.

## 4. Edit one batch

Choose one coherent owner-boundary batch. Delete obsolete test-only exports, globals, flags, wrappers, injection parameters and dead production paths instead of preserving aliases. Move retained regressions to their canonical owner. Collapse repeated package or dependency assertions into one generic contract.

Prefer a net reduction in production code. Add no replacement test that restates the same implementation, and leave uncertain candidates untouched rather than converting them into cleanup.

For each contract whose proof moved to another test, make one deliberate mutation of the production owner, confirm the keeper goes red, then restore the source byte for byte.

**Done:** the batch is applied and every moved contract has a caught mutation.

## 5. Validate

Stop any watch-mode or running test process on the checkout before editing, and keep tests that create temporary repositories, servers or processes stopped until their cleanup finishes.

1. Run the smallest owner and sibling tests with the project's runner.
2. For a removed source grep or plan assertion, run the executable, script or dry run that owns the real contract.
3. Run the project's formatter on changed files and a whitespace diff check.
4. Run the changed-files or aggregate gate the project requires for this change.
5. Report `git diff --numstat` with production and tooling separated from tests and test support.
6. Review the final diff with the `code-review` skill when available.

**Done:** each command's result is recorded; an unavailable gate is named with its reason.

## 6. Land and continue

Commit, push, open a pull request or land only with authority for that action, following the project's flow (and the `git-commit` skill when available). Land one coherent batch at a time; after it lands, refresh from the current base and rerun discovery for the next batch.

## Handoff

Report:

- root cause and the removed low-value categories;
- production owner simplifications;
- retained false positives and why they remain valuable;
- baseline failures and whether each is a product defect;
- focused and full checks actually run, with pass, fail or skip;
- production versus test line counts;
- copies elsewhere left for their owner, and the landing state;
- named follow-ups.
