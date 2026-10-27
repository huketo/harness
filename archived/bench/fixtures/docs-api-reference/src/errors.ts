/**
 * Base class of every error this library throws.
 *
 * Every instance carries a machine-readable `code` so callers can branch
 * without matching on message text.
 */
export class FeedError extends Error {
  readonly code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = "FeedError";
    this.code = code;
  }
}

/** Thrown when a single attempt exceeds `requestTimeoutMs`. */
export class FeedTimeoutError extends FeedError {
  readonly timeoutMs: number;

  constructor(timeoutMs: number) {
    super(`request timed out after ${timeoutMs}ms`, "feed_timeout");
    this.name = "FeedTimeoutError";
    this.timeoutMs = timeoutMs;
  }
}

/**
 * Thrown when a response body is not a well-formed feed record: unparseable
 * JSON, or a record missing any of `id`, `topic`, `body`, `revision`.
 */
export class FeedDecodeError extends FeedError {
  readonly received: string;

  constructor(received: string) {
    super("response body is not a feed record", "feed_decode");
    this.name = "FeedDecodeError";
    this.received = received;
  }
}

/** Thrown when a closed client is used again. */
export class FeedClosedError extends FeedError {
  constructor() {
    super("client is closed", "feed_closed");
    this.name = "FeedClosedError";
  }
}
