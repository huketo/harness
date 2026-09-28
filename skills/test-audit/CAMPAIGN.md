# Test-pruning campaign

A campaign prunes one component's whole test surface in one change: a plugin, a package or one core area. The retention bar, candidate evidence and validation in [SKILL.md](SKILL.md) apply to every lane. This file adds the order of work; each step ends on its completion criterion, and the next step starts only after it.

## 1. Baseline

Pin the base revision. Record the component's test and test-support line counts, its production line count separately, and every test file's pass or fail state. Keep baseline failures in their own list: in the upstream campaign that shaped this procedure, all three baseline failures were real product bugs.

**Done:** every in-scope test file has a recorded baseline result.

## 2. Lanes

Split the surface into lanes along production owner boundaries, not file prefixes (for a messaging plugin: accounts, commands, dispatch, inbound, outbound, persistence, transport, shared harness, live scenarios). Include the component's cases in shared core suites and its QA or live-proof harness tests.

**Done:** every test file and scenario the component owns belongs to exactly one lane.

## 3. Ledger per lane

Give each lane to its own read-only agent. It reads every assigned test in full, including parameter tables, plus the production owners, entry points, callers, history and CI routing. Each test declaration gets one mark; a table-driven test is one declaration unless its rows need different marks.

- `R` retain, naming the contract and the bug it catches (a move to a better file stays `R` with the move noted);
- `F` retain the contract but repair the assertion, such as a negative that passes when only one of several items is missing;
- `C` consolidate, naming the owner that absorbs the assertion first;
- `D` delete, naming the remaining proof or why no contract exists.

**Done:** every declaration in the lane has a mark and an evidence line.

## 4. Layer plan

Treat the ledger as input, not the edit list. A second read-only pass looks for a redundant layer: several suites replaying one shared helper through the same mock around a stronger real-boundary suite. Name the keeper suite for each contract, preferring the real transport boundary with a fake network over a mocked collaborator. Correct ledger errors found here.

**Done:** each lane plan names its retired files, its keeper per contract, the assertions to carry into keepers and the test-only seams unlocked.

## 5. Cutover

Edit lane by lane. Serialize changes to shared harnesses and support files through one owner. With each lane, remove the test-only seams it unlocks: injection parameters, getters, reset exports and indirection layers. Register moved suites in CI routing and test inventories, and update any size baselines the project enforces. Put durable test-ownership rules, drawn from mistakes this campaign actually found, in the component's agent instructions.

**Done:** every lane plan is applied and each lane's keepers pass.

## 6. Preservation review

Independent reviewers, one per boundary group, compare deleted coverage against the keepers. They look for contracts that lost their only proof and for new assertions that cannot fail. For each restored contract, mutate the production owner once, confirm the keeper goes red, and restore the source byte for byte.

**Done:** every reported gap is restored or rejected with source evidence, and every restored contract has a caught mutation.

## 7. Product defects

A baseline failure that survives into a keeper is a bug report. Fix it at its owner in a separate commit and prove it through the real user flow, with a control run that reverts the fix and shows the old behavior. Record unrelated product discrepancies as follow-ups.

**Done:** each repaired defect has a failing control and a passing candidate on the same harness.

## 8. Reconcile and hand off

A long campaign outlives many base commits. Integrate the base branch by the project's policy; when the base modified a file the campaign deleted, keep the deletion and port the new contract into its keeper. Confirm every regression the base added still has a home, then rerun the whole component suite and any live proof on the merged head. Review tooling may truncate a diff this large; review lane by lane.

Hand off with the [SKILL.md](SKILL.md) report, plus:

- baseline and final test and support line counts, with production counted separately;
- lanes, retired layers and keepers;
- preservation gaps found and their mutations;
- product defects with control and candidate proof.
