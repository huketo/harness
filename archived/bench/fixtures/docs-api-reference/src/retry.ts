import { FeedError } from "./errors.ts";

/** Total attempts made per request when the caller does not say otherwise. */
export const DEFAULT_RETRY_ATTEMPTS = 3;

const BASE_DELAY_MS = 250;
const MAX_DELAY_MS = 4000;

/**
 * Delay before the attempt numbered `attempt`, counting from 1.
 *
 * The delay doubles per attempt from a 250ms base and is capped at 4000ms, so
 * attempts 1..n wait 0, 250, 500, 1000, 2000, 4000, 4000, ... milliseconds.
 */
export function computeBackoffMs(attempt: number): number {
  if (attempt <= 1) {
    return 0;
  }
  return Math.min(BASE_DELAY_MS * 2 ** (attempt - 2), MAX_DELAY_MS);
}

/**
 * Run `task` until it resolves or the attempt budget is spent.
 *
 * Only `FeedError` is retried; any other rejection propagates immediately
 * because it signals a caller bug rather than a transport failure. The
 * rejection of the last attempt is the rejection of the returned promise.
 */
export async function retryWithBackoff<T>(
  task: (attempt: number) => Promise<T>,
  attempts: number = DEFAULT_RETRY_ATTEMPTS,
): Promise<T> {
  if (attempts < 1) {
    throw new RangeError("attempts must be at least 1");
  }
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const delayMs = computeBackoffMs(attempt);
    if (delayMs > 0) {
      const { promise, resolve } = Promise.withResolvers<void>();
      setTimeout(resolve, delayMs);
      await promise;
    }
    try {
      return await task(attempt);
    } catch (error) {
      if (!(error instanceof FeedError)) {
        throw error;
      }
      lastError = error;
    }
  }
  throw lastError;
}
