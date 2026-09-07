# Doubles and real dependencies

Keep the behavior under test real. Substitute a dependency to control an otherwise unavailable, expensive or nondeterministic boundary, not to dictate the implementation's private call graph.

| Contract | Appropriate boundary |
| --- | --- |
| Pure business calculation | Real function with explicit input, clock or seeded randomness |
| Payment/email failure handling | Fake or stub of the external provider with independently specified success and failure responses |
| SQL constraint, transaction, lock, query or migration | Real isolated database with the relevant engine semantics |
| Browser rendering/navigation | Real browser and application; controlled network boundary where allowed |
| End-to-end persistence, authentication or synchronization | Real owned services through the agreed integration harness |

State what a double omits. A fake payment provider can exercise a rejected charge path, but cannot prove compatibility with the live provider. Keep separate adapter/contract checks where that compatibility matters. A transaction rolled back by the test only isolates operations that actually use that transaction; separate HTTP connections and background workers may commit independently.

Prefer existing fixtures and dependency injection at a narrow boundary. A double may stand in for a module you own when it is outside this test's contract; use a real integration test for the boundary that was substituted. Choose specific or generic client interfaces according to the application's protocol, not solely to simplify mocking.

Each test owns its double's mutable history and behavior. Reset the state actually changed, including one-shot responses, stubs and external records. A global mock reset does not clean a database or cancel background work. Treat unexpected requests as failures with useful request details; catch-all successful responses create false coverage.

Sources: [Fowler, Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html) distinguishes state/interaction verification and classical/mockist tradeoffs; [Fowler, isolation](https://martinfowler.com/articles/nonDeterminism.html#LackOfIsolation) explains transaction rollback's limits; [Playwright network mocking](https://playwright.dev/docs/mock) documents controlled browser responses.
