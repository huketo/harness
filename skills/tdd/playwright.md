# Playwright reliability

Read the project's fixture import, config, projects and package script before running. Use that fixture, not a fresh import from `@playwright/test` that bypasses guards or setup.

## Observe the completed behavior

Prefer role/name, label and explicit test-ID contracts; scope ambiguous locators. Use awaited web-first assertions such as `await expect(locator).toBeVisible()`. `expect(await locator.isVisible()).toBe(true)` is an immediate sample, and `expect(array).toHaveLength(1)` does not acquire locator retry behavior.

A click performs actionability checks and dispatches input; it does not promise that every resulting request, queue consumer or render has finished. Register a request/response listener before the action if that event is the contract, then check its result. Otherwise await the stable UI result or poll the observable probe:

```ts
await submit.click();
await expect.poll(() => probe.orders.length).toBe(1);
expect(probe.orders[0].publicationRequired).toBe(false);
```

This observes the first order; it does not by itself prove no second order will occur. For an exactly-once contract, await the operation's completion before checking the final count. Keep clicks and writes outside `expect.poll` / `toPass` callbacks. A response alone does not prove the resulting DOM is ready.

Wait on application state rather than fixed `waitForTimeout`, `networkidle` or forced clicks. A transient toast is a valid target only when notification behavior is the contract; otherwise verify the durable result. If the toast itself is required, control its lifetime or capture the event without deleting its coverage.

## Own the environment

Browser contexts isolate cookies and browser storage, not server accounts, databases, filesystem, search indices or ports. Shared authentication state is suitable for independent read-only tests; mutating account state needs an owned account per worker/test as the contract requires. Keep authentication files and traces containing tokens out of version control.

Build each test's prerequisites independently, or express one inseparable journey in one test. Use fixtures with teardown after `use` and protect partial acquisition with cleanup. Release only owned records/resources. Test retries replace failed workers, so setup must also work after a worker restart.

Reserve distinct ports and data namespaces for separate invocations. `reuseExistingServer` checks availability, not the intended revision; verify ownership or fail on an unexpected server. Use the same origin source for `baseURL` and `webServer.url`, and ensure variables required by workers reach workers, not just `webServer.env`. Health/readiness must establish the dependencies the scenario actually uses.

Browser `page.route` does not intercept server-side application fetches. Use the repository's server-side double or real integration harness for those calls. Treat unexpected requests and incomplete fixture setup as failures rather than supplying catch-all success.

## Diagnose without hiding the first failure

Preserve the configured browser projects and flake gate. A focused diagnostic command can append supported options:

```text
<spec-file> --retries=0 --repeat-each=10 --trace=retain-on-failure
```

Choose the repetition count up front and record it with the worker count, config, revision and all failures. A diagnostic single-worker run can distinguish contention, but rerun with the original concurrency before claiming repair. With retries disabled, `trace: on-first-retry` captures no first failure; override it for that diagnostic run. `failOnFlakyTests` catches failed-then-passed attempts only when retries exist; it does not detect every latent flake.

Sources: [best practices](https://playwright.dev/docs/best-practices), [assertions](https://playwright.dev/docs/test-assertions), [authentication](https://playwright.dev/docs/auth), [fixtures](https://playwright.dev/docs/test-fixtures), [web servers](https://playwright.dev/docs/test-webserver), [retries](https://playwright.dev/docs/test-retries), [CLI](https://playwright.dev/docs/test-cli).
