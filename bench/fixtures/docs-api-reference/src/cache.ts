import type { FeedRecord } from "./types.ts";

/** Cache lifetime applied when an entry is stored without an explicit TTL. */
export const DEFAULT_CACHE_TTL_MS = 30000;

/** Number of entries kept before the least recently used one is evicted. */
export const DEFAULT_CACHE_CAPACITY = 128;

interface CacheEntry {
  record: FeedRecord;
  expiresAtMs: number;
}

/**
 * Bounded, time-aware record cache with least-recently-used eviction.
 *
 * Reads treat an expired entry as a miss and drop it, so a stale record is
 * never returned even if the entry has not been evicted yet.
 */
export class MemoryCache {
  private readonly entries = new Map<string, CacheEntry>();

  constructor(
    readonly capacity: number = DEFAULT_CACHE_CAPACITY,
    readonly defaultTtlMs: number = DEFAULT_CACHE_TTL_MS,
  ) {
    if (capacity < 1) {
      throw new RangeError("capacity must be at least 1");
    }
  }

  /** Store one record; `ttlMs` defaults to the cache's default TTL. */
  set(key: string, value: FeedRecord, ttlMs?: number): void {
    this.entries.delete(key);
    this.entries.set(key, {
      record: value,
      expiresAtMs: Date.now() + (ttlMs ?? this.defaultTtlMs),
    });
    while (this.entries.size > this.capacity) {
      const [oldest] = this.entries.keys();
      this.entries.delete(oldest);
    }
  }

  /** Return the live record for `key`, or `undefined` on miss or expiry. */
  get(key: string): FeedRecord | undefined {
    const entry = this.entries.get(key);
    if (entry === undefined) {
      return undefined;
    }
    if (entry.expiresAtMs <= Date.now()) {
      this.entries.delete(key);
      return undefined;
    }
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.record;
  }

  clear(): void {
    this.entries.clear();
  }

  /** Number of entries currently held, including expired ones. */
  get size(): number {
    return this.entries.size;
  }
}
