// This suite exercises real AbortSignal delivery against the platform clock:
// the behaviour under test is whether an interrupted backoff wait lets the loop
// continue, which fake timers would define away. Waits stay in the tens of
// milliseconds and the assertions compare against a wide upper bound.

import { describe, expect, test } from "bun:test";

import { backoffDelay, retry, RetryAbortedError, waitFor } from "../src/retry.ts";

describe("retry", () => {
  test("returns the first result without retrying", async () => {
    let calls = 0;
    const result = await retry(
      async (attempt) => {
        calls += 1;
        return `ok:${attempt}`;
      },
      { attempts: 3, baseDelayMs: 1 },
    );
    expect(result).toBe("ok:1");
    expect(calls).toBe(1);
  });

  test("retries until the operation succeeds", async () => {
    const seen: number[] = [];
    const result = await retry(
      async (attempt) => {
        seen.push(attempt);
        if (attempt < 3) {
          throw new Error(`attempt ${attempt} failed`);
        }
        return "recovered";
      },
      { attempts: 5, baseDelayMs: 1 },
    );
    expect(result).toBe("recovered");
    expect(seen).toEqual([1, 2, 3]);
  });

  test("rejects with the last error once the attempts are used up", async () => {
    let calls = 0;
    const attempt = retry(
      async (index) => {
        calls += 1;
        throw new Error(`failure ${index}`);
      },
      { attempts: 3, baseDelayMs: 1 },
    );
    await expect(attempt).rejects.toThrow("failure 3");
    expect(calls).toBe(3);
  });

  test("grows the delay exponentially", () => {
    expect(backoffDelay(20, 2, 1)).toBe(20);
    expect(backoffDelay(20, 2, 2)).toBe(40);
    expect(backoffDelay(20, 2, 3)).toBe(80);
  });

  test("never starts an attempt when the signal is already aborted", async () => {
    let calls = 0;
    const controller = new AbortController();
    controller.abort();
    const attempt = retry(
      async () => {
        calls += 1;
        return "unreachable";
      },
      { attempts: 3, baseDelayMs: 1, signal: controller.signal },
    );
    await expect(attempt).rejects.toBeInstanceOf(RetryAbortedError);
    expect(calls).toBe(0);
  });

  test("stops after the attempt that requested the cancellation", async () => {
    let calls = 0;
    const controller = new AbortController();
    const attempt = retry(
      async () => {
        calls += 1;
        controller.abort();
        throw new Error("cancelled mid-flight");
      },
      { attempts: 4, baseDelayMs: 5, signal: controller.signal },
    );
    await expect(attempt).rejects.toBeInstanceOf(RetryAbortedError);
    expect(calls).toBe(1);
  });

  test("reports the cancellation when the last attempt is the one cancelled", async () => {
    let calls = 0;
    const controller = new AbortController();
    const attempt = retry(
      async (index) => {
        calls += 1;
        if (index === 2) {
          controller.abort();
        }
        throw new Error(`attempt ${index} failed`);
      },
      { attempts: 2, baseDelayMs: 1, signal: controller.signal },
    );
    await expect(attempt).rejects.toBeInstanceOf(RetryAbortedError);
    expect(calls).toBe(2);
  });

  test("cancelling the backoff wait skips the remaining attempts", async () => {
    let calls = 0;
    const controller = new AbortController();
    setTimeout(() => controller.abort(), 20);
    const started = Date.now();
    const attempt = retry(
      async () => {
        calls += 1;
        throw new Error("still failing");
      },
      { attempts: 2, baseDelayMs: 2_000, signal: controller.signal },
    );
    await expect(attempt).rejects.toBeInstanceOf(RetryAbortedError);
    expect(calls).toBe(1);
    expect(Date.now() - started).toBeLessThan(1_000);
  });

  test("an aborted wait resolves early instead of rejecting", async () => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), 10);
    const started = Date.now();
    await waitFor(2_000, controller.signal);
    expect(Date.now() - started).toBeLessThan(1_000);
  });
});
