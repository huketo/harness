---
name: tdd
description: TDD for behavior changes; adding or changing tests, fixtures, isolation, waits, or runner configuration; fixing flaky or order-dependent tests with a known test-environment cause.
---

# Reliable TDD

Produce a test that detects the intended defect, a minimal change that passes it, and evidence from the relevant execution boundary. Repository rules own test placement, infrastructure and required gates.

## 1. Contract

Read the affected code, neighboring tests, runner configuration and applicable repository instructions. Use domain terminology and existing fixtures. List the requested behaviors; for each, name the observable result and smallest boundary that can detect a plausible defect. This list is analysis, not a batch of speculative test implementations.

Choose established boundaries autonomously. Ask only when unresolved product behavior, an interface tradeoff or authority actually needs a human decision. If another instruction blocks authorized work, quote its exact source and resolve the conflict rather than silently abandoning the task.

Read [tests.md](tests.md) before choosing assertions or reviewing coverage, and [mocking.md](mocking.md) before choosing doubles or integration boundaries. Read [vitest.md](vitest.md) for Vitest advice, edits or execution; read [playwright.md](playwright.md) for the equivalent Playwright work.

Choose assertions by the contract, not a blanket ban: durable storage may require direct SQL; exactly-once charging requires observing the external fake/provider's charge ledger or calls. A local order row cannot prove a provider was not charged twice.

**Done:** each requested behavior has an observation, a test location and a focused command; the required broader gates and infrastructure prerequisites are identified. Documentation-only changes need document validation, not invented behavioral tests.

## 2. Isolation

For every mutable dependency the run reaches, identify its owner, starting state and cleanup: database, cache, account, search index, filesystem, ports, processes, globals, clock and randomness. A worktree, worker process or browser context does not isolate external state.

Use the repository's provisioning path and explicit per-command environment. Establish owned resources before launching parallel runs; preserve configured serialization until the shared resource is isolated. Cleanup must run after failure and partial setup, stop producers before deleting their data, and affect only this run's resources. Surface cleanup failures. A resource that cannot safely be isolated must have an explicit exclusive owner.

**Done:** the command cannot reset or attach to another run's mutable resources; all acquired resources have failure-safe disposal. If ownership is unknown, stop that execution path and finish safe local work.

## 3. Red

Implement one test from the behavior list and run it before changing production behavior. Confirm it fails because the intended result is absent or wrong. A discovery, import, setup or infrastructure failure is not behavioral red; fix the prerequisite and rerun. For a new API, a missing symbol is an intermediate signal: reach an executable assertion before claiming the behavior is tested.

For an existing intermittent failure, preserve the reported signature and first-failure artifacts; do not rerun merely to confirm the report. Build the smallest controlled reproduction that distinguishes hypotheses. Prefer explicit gates, a controlled clock, deterministic scheduling or a seeded input to timing guesses. A passing retry establishes non-determinism, not whether the defect is in product code, a test or infrastructure. When reproduction remains unavailable, report the exact unexercised path and missing evidence; do not label a speculative change a fix.

**Done:** an executed command and its failing assertion demonstrate the intended defect. Record the runner/config, seed or schedule, and failure output; avoid copying credentials into evidence.

## 4. Green, then refactor

Make the minimal source change that satisfies the same assertion. Keep the contract intact: a retry, skip, permissive assertion, swallowed error, blanket timeout increase or forced serialization is not a root-cause repair. Adjust a budget only when measured legitimate work justifies it; preserve its finite deadline and diagnostic failure.

Synchronize on the promised state. Await completion when an API promises completion; polling there can hide a broken promise. For an eventually consistent API, use a bounded, observational poll with the last observed state/error in its failure. Keep writes and clicks outside retry callbacks. A negative assertion needs a completed opportunity for the forbidden effect to occur.

After green, refactor the touched code and test when it improves the next change; rerun the relevant tests after each meaningful refactor. Continue one red-green-refactor slice at a time until the behavior list is covered. Refactoring is part of TDD, not deferred to code review.

**Done:** the same regression passes without weakening its oracle, and relevant existing tests remain green after refactoring.

## 5. Verify and hand off

Run the affected file and relevant suite with the repository's normal configuration. Check that the intended tests actually executed: exit zero with zero tests, all skipped, a mocked path instead of the claimed integration, or a different server build is not proof.

For a flake repair, rerun the controlled trigger and the original failing scope with retries disabled where supported. Choose a finite repetition count and the relevant variation (file order, seed, fresh process, owned parallel workers or delayed dependency) before the run. Keep every failure; do not rerun until green. Finite clean runs are bounded evidence, never proof of zero flakiness. Run broader required gates once the edits settle; broaden further only for a changed risk or new failure.

Report the behavior covered, red/green command results, actual execution counts, runner/config and seed, first-attempt failures versus retry passes, and unrun gates with reasons. Label a manually injected mutant or simulated schedule as such. Quarantine is a separately authorized, tracked coverage loss with an owner, expiry and exit criterion; preserve the normal failure gate by default.

**Done:** all requested behaviors and required gates are accounted for, original failure evidence has a corresponding verification or explicit blocker, and temporary probes and owned resources are cleaned up. Distinguish a local pass from CI evidence for the exact delivered revision.

## Sources

- [Kent Beck, Canon TDD](https://newsletter.kentbeck.com/p/canon-tdd): behavior list, one runnable test, green, optional refactor, repeat.
- [Martin Fowler, TDD](https://martinfowler.com/bliki/TestDrivenDevelopment.html): refactoring belongs in the cycle.
- [Fowler, Eradicating Non-Determinism](https://martinfowler.com/articles/nonDeterminism.html): isolation, asynchronous behavior, remote services, time and resource leaks.
- [Google, Flaky Tests at Google](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html): retries and quarantine can mask real races.
