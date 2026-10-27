# Changelog

## 3.0.0

Breaking release. The public surface was renamed and trimmed; nothing in this
release keeps a compatibility alias.

- Renamed `createClient` to `createFeedClient`. The options object is unchanged.
- Renamed `LruCache` to `MemoryCache`. The constructor now takes
  `(capacity, defaultTtlMs)` instead of a single options object.
- Removed `FeedWarning`. Recoverable transport problems are reported as
  `FeedTimeoutError` or `FeedDecodeError`, both of which extend `FeedError`.
- Removed `flushAllCaches`. A cache is owned by the client that created it, so
  clearing every cache from module scope is no longer possible; call
  `FeedClient.invalidate` or `MemoryCache.clear` instead.
- `FeedError` now carries a `code` string on every instance.
- Added `FeedClosedError`. Using a client after `close` now throws inside the
  `FeedError` hierarchy instead of a bare `Error`.

## 2.4.0

- Added `computeBackoffMs` so callers can predict the retry schedule.
- Raised the retry delay cap to 4000ms.

## 2.3.0

- Added `FeedWarning` for transport problems that did not fail the request.
- Added `flushAllCaches` for test teardown.

## 2.0.0

- Introduced `createClient`, `LruCache`, and the `FeedError` hierarchy.
