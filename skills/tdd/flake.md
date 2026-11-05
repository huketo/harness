# Flake prevention

Read this when a new or changed test crosses an async boundary: a browser, request, timer, queue, worker, second connection or process. A synchronous test of in-memory state skips it.

Most flaky tests are flaky from their first commit, so the cheapest moment to shake one is before it lands.

## Name the orderings

Write each ordering the test relies on as `A before B`: which state must exist before each action and each assertion. Two actors started together (`Promise.all`, a second request, an input sent as soon as something appears) count as an ordering until the test fixes it.

Enforce each ordering with a gate or a promised completion: await the entry signal of the first actor, hold a lock both must reach, or observe the durable result. An ordering that holds only because one side is usually faster is a race, however green it runs.

## Burn in

1. Declare the conditions and counts before the first run. Retries are off, and the run uses the original assertions.
2. For each named ordering, delay the earlier side at that exact point and run again. In the measured corpus this reproduced one race on every run after broad load, shuffling and running alone all missed it. A delay is a temporary probe; remove it afterwards.
3. Run the runner's matrix in [playwright.md](playwright.md#burn-in-a-new-test) or [vitest.md](vitest.md#burn-in-a-new-test). The conditions are complementary. In the measured corpus, slowing a page exposed a test that outran the page and hid input that outran the page's startup, so one condition alone can stay green on a real race.
4. Keep every failure. Choose the count from the failure rate worth catching: detection is `1-(1-p)^N`, so 20 runs catch a 15% race 96% of the time and a 3% race 46% of the time.

A failure under these conditions is a defect until diagnosed: none of them failed a repaired test in the measured corpus. Tightening a timeout is different: it failed repaired tests too, so it is not a burn-in condition. Test the product hypothesis first, since a test that loses early input may be reporting a product that loses it for people too. A clean burn-in is bounded evidence; report conditions, counts and failures.

## Patterns

| Pattern | Signature | Repair |
| --- | --- | --- |
| Unpromised order | Two actors start together, and the assertion assumes who wins | Gate the first actor's entry, or hold both at the serialization point |
| Deadline race | A zero or tiny timeout must beat real I/O | Stall the dependency so only the deadline can fire |
| Late listener | The UI announces a state, then attaches its handler; input sent on the announcement is lost | Wait until the queued work has run, or fix the product's readiness |
| Early input | Input lands before the first effect and is overwritten | Fix the product; the test is reporting a real loss |
| Early sample | A probe is read once right after an unrelated assertion | Poll the probe, or register the wait before the action |
| Navigation in flight | The test navigates while the previous response is pending | Wait for that response's durable result first |
| Mutable teardown handle | Teardown reads reassigned handles after an `await`, then closes the next case's | Capture the handles before the first `await` |
| Ambient observer | A listener records every request and counts ones the subject never sent | Filter by owner, or observe the subject's own call |

## Promote a repeated pattern

The second occurrence of a pattern in one repository moves from prose into that repository's lint rule, fixture or helper. Its error message names the repair. Prove the check by rejecting the bad case and accepting a valid one. Where no mechanical check can see the pattern, add the safe shape to the shared fixture so the correct test is the shortest one to write.
