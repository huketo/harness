# Assertions at the contract boundary

Select the smallest boundary that exposes the behavior. A pure function can defend a pricing rule; a real database adapter must defend SQL constraints and transaction behavior; a browser flow must defend navigation and rendering. No one layer substitutes for all three.

Use independent expected values: a worked example, specification, invariant or known fixture. State the observable difference a plausible defect would cause. Keep related assertions together when they describe one outcome; assertion count is not a quality measure.

## Behavior versus implementation

Prefer observable results over private call chains, incidental defaults and large snapshots. Mock echoes and source-text searches do not establish runtime behavior. A protocol field, exact copy or ordering deserves an assertion when it is part of the requested contract, not merely because it appears in today's implementation.

A direct database assertion is appropriate when durable state, atomicity or a constraint is the contract. Reading back through an in-memory cache would not prove durability. At a UI boundary, prefer the visible result; do not claim database persistence from a mocked HTTP response.

Interaction assertions can defend an external protocol: exactly one charge, no delivery to an unauthorized recipient, or required ordering of a commit and its publication. Explain the contract rather than banning all call counts or asserting each private method call.

## Boundaries and transitions

- For expiration or backoff, control time and test the boundary on both sides; elapsed wall time is a separate performance concern.
- For idempotency, exercise the duplicate operation and assert the durable/external outcome, not just a cache field.
- For eventual state, poll a read with a deadline and inspect the expected value. For promised completion, read immediately after awaiting that promise.
- For forbidden effects, complete the triggering operation or drive the defined observation window before asserting absence. An empty array immediately after a click proves only that the array is empty now.
- For multi-step scenarios, either keep the journey in one test or build each test's prerequisites independently. Tests in separate cases should not rely on previous cases creating their data.

## Red as an oracle check

A test passing on both the buggy and repaired implementation needs a stronger oracle. If the original bug cannot safely be reinstated, a focused mutant can check sensitivity; distinguish that evidence from reproducing the incident. Never weaken the required behavior to make a test green. When removing an implementation-coupled assertion, preserve any real contract it happened to cover at the appropriate boundary.

Sources: [Canon TDD](https://newsletter.kentbeck.com/p/canon-tdd), [Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html), [Playwright testing philosophy](https://playwright.dev/docs/best-practices#testing-philosophy).
