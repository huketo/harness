/** One immutable feed record as stored by the upstream service. */
export interface FeedRecord {
  /** Stable record identifier, unique per topic. */
  id: string;
  /** Topic the record belongs to. */
  topic: string;
  /** Decoded record payload. */
  body: string;
  /** Monotonic revision counter; a higher value wins on conflict. */
  revision: number;
}

/** Construction options for a feed client. */
export interface FeedClientOptions {
  /** Absolute base URL of the feed service, without a trailing slash. */
  baseUrl: string;
  /** Cache lifetime for one record, in milliseconds. */
  cacheTtlMs?: number;
  /** Maximum number of records held in the client cache. */
  cacheCapacity?: number;
  /** Total attempts per request, including the first one. */
  retryAttempts?: number;
  /** Per-attempt deadline, in milliseconds. */
  requestTimeoutMs?: number;
}
