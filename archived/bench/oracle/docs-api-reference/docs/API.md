# feed-client API reference

`feed-client` 3.0.0 reads immutable feed records over HTTP, caches them for a
bounded time, and retries transport failures with exponential backoff.

The package entry point is `src/index.ts`; every name below is exported from it
and no other name is public. Version 3.0.0 renamed two of these names and
removed two others, so code written against 2.x needs the migration notes at
the end of this document and in `CHANGELOG.md`.

```ts
import { createFeedClient } from "feed-client";

const client = createFeedClient({ baseUrl: "https://feed.example/v1" });
const record = await client.getRecord("record-42");
client.close();
```

## FeedClient

```ts
export class FeedClient {
  constructor(options: FeedClientOptions);
  async getRecord(id: string): Promise<FeedRecord | null>;
  async listRecords(ids: readonly string[]): Promise<FeedRecord[]>;
  invalidate(): void;
  close(): void;
}
```

Read-through client for the feed service. Every read consults the cache first
and then the retry policy. The client owns its cache, so `close` is the only
way to release it.

- `constructor(options: FeedClientOptions)` normalizes `baseUrl` by dropping
  trailing slashes and builds the cache from `cacheCapacity` and `cacheTtlMs`.
- `getRecord` resolves from the cache without issuing a request when a live
  entry exists, and resolves `null` when the service has no such record.
- `listRecords` preserves the input order and skips records the service does
  not have; it reads through `getRecord`, so it shares the cache.
- `invalidate` drops every cached record and keeps the client usable.
- `close` clears the cache; every later read rejects with `FeedClosedError`.

A response body that is not parseable JSON, or a record missing any of `id`,
`topic`, `body`, `revision`, raises `FeedDecodeError`. An attempt that exceeds
`requestTimeoutMs` raises `FeedTimeoutError`.

## createFeedClient

```ts
export function createFeedClient(options: FeedClientOptions): FeedClient;
```

Builds a client from plain options. Equivalent to `new FeedClient(options)`;
prefer it when the options come from configuration.

## FeedClientOptions

```ts
export interface FeedClientOptions {
  baseUrl: string;
  cacheTtlMs?: number;
  cacheCapacity?: number;
  retryAttempts?: number;
  requestTimeoutMs?: number;
}
```

Only `baseUrl` is required; it is an absolute URL without a trailing slash.
`cacheTtlMs` defaults to `DEFAULT_CACHE_TTL_MS`, `cacheCapacity` to
`DEFAULT_CACHE_CAPACITY`, `retryAttempts` to `DEFAULT_RETRY_ATTEMPTS`, and
`requestTimeoutMs` to 2000, the per-attempt deadline.

## FeedRecord

```ts
export interface FeedRecord {
  id: string;
  topic: string;
  body: string;
  revision: number;
}
```

One immutable record as stored upstream. `id` is unique per `topic`, and
`revision` is a monotonic counter whose higher value wins on conflict. All four
fields are required: a response missing any of them is a `FeedDecodeError`.

## MemoryCache

```ts
export class MemoryCache {
  constructor(
    readonly capacity: number = DEFAULT_CACHE_CAPACITY,
    readonly defaultTtlMs: number = DEFAULT_CACHE_TTL_MS,
  );
  set(key: string, value: FeedRecord, ttlMs?: number): void;
  get(key: string): FeedRecord | undefined;
  clear(): void;
  get size(): number;
}
```

Bounded, time-aware record cache with least-recently-used eviction. A read
treats an expired entry as a miss and drops it, so a stale record is never
returned even when the entry has not been evicted yet. The constructor throws
`RangeError` when `capacity` is below 1.

- `set` stores one record; `ttlMs` defaults to `defaultTtlMs`, and re-inserting
  a key refreshes its recency.
- `get` returns `undefined` on a miss or an expiry.
- `clear` drops every entry.
- `size` counts the entries currently held, expired ones included.

## DEFAULT_CACHE_TTL_MS

```ts
export const DEFAULT_CACHE_TTL_MS = 30000;
```

The cache lifetime, in milliseconds, applied when an entry is stored without an
explicit TTL. Thirty seconds.

## DEFAULT_CACHE_CAPACITY

```ts
export const DEFAULT_CACHE_CAPACITY = 128;
```

The number of entries a cache keeps before the least recently used one is
evicted.

## FeedError

```ts
export class FeedError extends Error {
  readonly code: string;
  constructor(message: string, code: string);
}
```

Base class of every error this library throws. Each instance carries a
machine-readable `code`, so callers branch on `code` instead of matching
message text. The constructor sets `name` to `"FeedError"`.

## FeedTimeoutError

```ts
export class FeedTimeoutError extends FeedError {
  readonly timeoutMs: number;
  constructor(timeoutMs: number);
}
```

Thrown when a single attempt exceeds `requestTimeoutMs`. Its `code` is
`"feed_timeout"` and `timeoutMs` is the deadline that expired.

## FeedDecodeError

```ts
export class FeedDecodeError extends FeedError {
  readonly received: string;
  constructor(received: string);
}
```

Thrown when a response body is not a well-formed feed record: unparseable JSON,
or a record missing any of `id`, `topic`, `body`, `revision`. Its `code` is
`"feed_decode"` and `received` is the raw response body that failed to decode.

## FeedClosedError

```ts
export class FeedClosedError extends FeedError {
  constructor();
}
```

Thrown when a client is used after `close`. Its `code` is `"feed_closed"` and
it carries no extra field. Only the client throws it; `MemoryCache` has no
closed state.

## retryWithBackoff

```ts
export async function retryWithBackoff<T>(
  task: (attempt: number) => Promise<T>,
  attempts: number = DEFAULT_RETRY_ATTEMPTS,
): Promise<T>;
```

Runs `task` until it resolves or the attempt budget is spent. `attempts` must
be at least 1, otherwise `RangeError` is thrown. Only a `FeedError` rejection
is retried; any other rejection propagates immediately because it signals a
caller bug rather than a transport failure. When every attempt fails, the
rejection of the last attempt is the rejection of the returned promise.

## computeBackoffMs

```ts
export function computeBackoffMs(attempt: number): number;
```

Delay before the attempt numbered `attempt`, counting from 1. The first attempt
waits 0 ms, the second waits the 250 ms base, and each further attempt doubles
the delay up to the 4000 ms cap:

| `attempt` | 1 | 2 | 3 | 4 | 5 | 6 | 7+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| delay (ms) | 0 | 250 | 500 | 1000 | 2000 | 4000 | 4000 |

## DEFAULT_RETRY_ATTEMPTS

```ts
export const DEFAULT_RETRY_ATTEMPTS = 3;
```

The total number of attempts made per request, the first attempt included, when
the caller passes no `attempts` argument. With the default schedule the third
attempt starts about 750 ms after the first.

## Removed and renamed names

`CHANGELOG.md` is the normative list. In 3.0.0:

- `createClient` became `createFeedClient`, with the same options object.
- `LruCache` became `MemoryCache`, and its constructor now takes
  `(capacity, defaultTtlMs)` rather than one options object.
- Two 2.x names were dropped with no replacement export. Recoverable transport
  problems surface as `FeedTimeoutError` or `FeedDecodeError`, and a cache is
  cleared through `FeedClient.invalidate` or `MemoryCache.clear`.

No compatibility aliases remain in 3.0.0.
