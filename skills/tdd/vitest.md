# Vitest reliability

Read the installed version, package script and config before copying flags from current documentation. Preserve the package script's setup, aliases and serialization when narrowing a run.

## Async and time

Await promise assertions (`resolves`, `rejects`, `expect.poll`) and return/await the operation under test. A callback the runner never waits for can report green before its assertion executes.

For eventual state, use `await expect.poll(() => readState(), { timeout, interval }).toEqual(expected)` or the repository's equivalent. Poll reads only. Prefer the actual completion promise when one exists. Do not replace a diagnostic state diff with `expect(await pollBoolean()).toBe(true)`.

For example, within one integration test, await a successful DB commit and read it from a fresh appropriate connection immediately. Do not make a later test depend on this row or poll away a broken committed-read contract. Background indexing is different: its consumer may legitimately be eventual.

Use an injected clock or fake timers for timer logic; use real timers for real network/database work. `vi.setSystemTime` changes the clock without firing timers. Advance timers explicitly, using async timer APIs when callbacks schedule promise work. Pair fake time with `vi.useRealTimers()` in failure-safe teardown. Stop/cancel the owned operation before restoring time; blindly running all pending timers can execute unintended side effects or loop forever on an interval.

## Restore what changed

| Change | Matching restoration |
| --- | --- |
| Mock call history | `vi.clearAllMocks()`; retains implementations |
| Mock implementation/one-shot responses | Reset the relevant mock and reestablish this test's behavior |
| `vi.spyOn` property replacement | `vi.restoreAllMocks()`; does not restore automocked modules or fake timers |
| `vi.stubEnv` / `vi.stubGlobal` | `vi.unstubAllEnvs()` / `vi.unstubAllGlobals()` |
| Fake timers/system time | `vi.useRealTimers()` |
| Mutable store/cache | Fresh instance or existing reset fixture |
| DB/cache/file/server state | The owning fixture's disposal/reset |

Direct assignments to `process.env` or globals need their own restoration; unstub helpers only undo their own stubs. `vi.resetModules()` clears the module cache but does not reevaluate existing static imports or clear the mock registry. Hoisted `vi.mock` factories need `vi.hoisted` state or a suitable existing pattern; do not add reset APIs to production merely to hide test coupling.

## Concurrency

Vitest normally isolates files, including with the threads pool. Neither forks nor `isolate: true` isolates a database, port or cache. `fileParallelism: false` serializes files in this invocation only; it does not coordinate another agent's run. Concurrent tests in one file share a worker and globals, so fake timers, environment mutation and shared singleton mocks cannot be independently owned there. Keep those tests serial or change the fixture boundary before enabling concurrency.

Apply both ownership levels: keep global-mutating tests non-concurrent inside a file, and give each invocation its own external database (or an exclusive lease). File serialization alone does not stop `test.concurrent`, and unique row IDs do not protect against another test's whole-database `TRUNCATE`. Transaction rollback is insufficient for a contract involving independent commits or background connections.

Use test-context `expect` and test-local cleanup/fixtures when running concurrent tests that use assertion accounting. Do not rely on a global cleanup hook to distinguish another concurrent test's resources.

## Focused verification

Use the project's non-watch test command with a file filter; inspect execution counts even when the script allows no tests. For an order-dependency probe, append supported options to that command:

```text
--retry=0 --sequence.shuffle --sequence.seed=441
```

Verify every proposed flag against the installed runner's `--help` or version-matched API. If that lookup is unavailable, label the command unverified and omit guessed options. `--sequence.seed` requires shuffle to affect ordering; repeating the same seed is not varying the order.

Record the seed. Preserve any `--fileParallelism=false` required by external fixtures. Use several explicit seeds or fresh process runs only when diagnosing that risk. Vitest's retry is not Playwright's repeat-each; use a finite command runner for repetitions and preserve every exit status. A passing seed does not prove order independence.

Sources: [parallelism](https://vitest.dev/guide/parallelism), [Vi API](https://vitest.dev/api/vi), [expect.poll](https://vitest.dev/api/expect#poll), [test context](https://vitest.dev/guide/test-context), [sequence](https://vitest.dev/config/sequence).
