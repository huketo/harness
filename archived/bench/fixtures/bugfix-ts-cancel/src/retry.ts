/**
 * Retry helper with exponential backoff.
 *
 * The caller passes an `AbortSignal` to stop a retry loop that is no longer
 * useful, for example because the surrounding request already timed out.
 */

export interface RetryOptions {
  /** How many times the operation may run in total. Must be at least 1. */
  attempts: number;
  /** Delay before the second attempt, in milliseconds. */
  baseDelayMs: number;
  /** Growth factor of the backoff delay. Defaults to 2. */
  factor?: number;
  /** Cancels the retry loop. */
  signal?: AbortSignal;
}

/** Rejection reason of a retry loop that was cancelled through its signal. */
export class RetryAbortedError extends Error {
  constructor(message = "the retry loop was aborted") {
    super(message);
    this.name = "RetryAbortedError";
  }
}

/** Delay in milliseconds to wait after the given 1-based attempt failed. */
export function backoffDelay(baseDelayMs: number, factor: number, attempt: number): number {
  if (baseDelayMs < 0) {
    throw new RangeError("baseDelayMs must not be negative");
  }
  return baseDelayMs * factor ** (attempt - 1);
}

/**
 * Waits for `ms` milliseconds, or until `signal` aborts, whichever comes
 * first. A cancelled wait resolves instead of rejecting, so that the caller
 * decides what a cancellation means.
 */
export function waitFor(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => {
    const finish = (): void => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", finish);
      resolve();
    };
    const timer = setTimeout(finish, ms);
    signal?.addEventListener("abort", finish, { once: true });
  });
}

/**
 * Runs `operation` until it resolves or the attempts are used up, waiting an
 * exponentially growing delay between attempts.
 *
 * The operation receives the 1-based attempt number. When the signal aborts,
 * the loop stops and the returned promise rejects with `RetryAbortedError`.
 */
export async function retry<T>(
  operation: (attempt: number) => Promise<T>,
  options: RetryOptions,
): Promise<T> {
  const { attempts, baseDelayMs, factor = 2, signal } = options;
  if (!Number.isInteger(attempts) || attempts < 1) {
    throw new RangeError("attempts must be an integer of at least 1");
  }
  if (signal?.aborted) {
    throw new RetryAbortedError();
  }

  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await operation(attempt);
    } catch (error) {
      lastError = error;
      if (attempt === attempts) {
        break;
      }
      await waitFor(backoffDelay(baseDelayMs, factor, attempt), signal);
    }
  }
  throw lastError;
}
