/**
 * Demo entry point: `bun run src/index.ts`.
 *
 * A synthetic job fails twice before it succeeds, and a second run is
 * cancelled halfway through the backoff wait.
 */

import { retry, RetryAbortedError } from "./retry.ts";

async function main(): Promise<void> {
  let calls = 0;
  const flaky = async (attempt: number): Promise<string> => {
    calls += 1;
    if (attempt < 3) {
      throw new Error(`attempt ${attempt} failed`);
    }
    return `settled on attempt ${attempt}`;
  };

  const outcome = await retry(flaky, { attempts: 5, baseDelayMs: 10 });
  console.log(`${outcome} after ${calls} call(s)`);

  const controller = new AbortController();
  let cancelledCalls = 0;
  setTimeout(() => controller.abort(), 20);
  try {
    await retry(
      async () => {
        cancelledCalls += 1;
        throw new Error("still failing");
      },
      { attempts: 4, baseDelayMs: 500, signal: controller.signal },
    );
  } catch (error) {
    const label = error instanceof RetryAbortedError ? "cancelled" : "failed";
    console.log(`second run ${label} after ${cancelledCalls} call(s)`);
  }
}

await main();
