import { DEFAULT_CACHE_CAPACITY, DEFAULT_CACHE_TTL_MS, MemoryCache } from "./cache.ts";
import { FeedClosedError, FeedDecodeError, FeedTimeoutError } from "./errors.ts";
import { DEFAULT_RETRY_ATTEMPTS, retryWithBackoff } from "./retry.ts";
import type { FeedClientOptions, FeedRecord } from "./types.ts";

const DEFAULT_REQUEST_TIMEOUT_MS = 2000;

/**
 * Read-through client for the feed service.
 *
 * Every read goes through the cache first, then through the retry policy. The
 * client owns its cache, so `close` is the only way to release it.
 */
export class FeedClient {
  private readonly cache: MemoryCache;
  private readonly baseUrl: string;
  private readonly retryAttempts: number;
  private readonly requestTimeoutMs: number;
  private closed = false;

  constructor(options: FeedClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.retryAttempts = options.retryAttempts ?? DEFAULT_RETRY_ATTEMPTS;
    this.requestTimeoutMs = options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
    this.cache = new MemoryCache(
      options.cacheCapacity ?? DEFAULT_CACHE_CAPACITY,
      options.cacheTtlMs ?? DEFAULT_CACHE_TTL_MS,
    );
  }

  /**
   * Return the record for `id`, or `null` when the service has no such
   * record. A cached record is returned without a request.
   */
  async getRecord(id: string): Promise<FeedRecord | null> {
    if (this.closed) {
      throw new FeedClosedError();
    }
    const cached = this.cache.get(id);
    if (cached !== undefined) {
      return cached;
    }
    const record = await retryWithBackoff(async () => this.request(id), this.retryAttempts);
    if (record !== null) {
      this.cache.set(record.id, record);
    }
    return record;
  }

  /** Return the records for `ids` in input order, skipping missing ones. */
  async listRecords(ids: readonly string[]): Promise<FeedRecord[]> {
    const found: FeedRecord[] = [];
    for (const id of ids) {
      const record = await this.getRecord(id);
      if (record !== null) {
        found.push(record);
      }
    }
    return found;
  }

  /** Drop every cached record without closing the client. */
  invalidate(): void {
    this.cache.clear();
  }

  /** Release the cache and reject every later read. */
  close(): void {
    this.closed = true;
    this.cache.clear();
  }

  private async request(id: string): Promise<FeedRecord | null> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/records/${encodeURIComponent(id)}`);
    if (response.status === 404) {
      return null;
    }
    const body = await response.text();
    let payload: unknown;
    try {
      payload = JSON.parse(body);
    } catch {
      throw new FeedDecodeError(body);
    }
    const record = payload as Partial<FeedRecord> | null;
    if (
      typeof record !== "object" ||
      record === null ||
      typeof record.id !== "string" ||
      typeof record.topic !== "string" ||
      typeof record.body !== "string" ||
      typeof record.revision !== "number"
    ) {
      throw new FeedDecodeError(body);
    }
    return record as FeedRecord;
  }

  private async fetchWithTimeout(url: string): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.requestTimeoutMs);
    try {
      return await fetch(url, { signal: controller.signal });
    } catch (error) {
      if (controller.signal.aborted) {
        throw new FeedTimeoutError(this.requestTimeoutMs);
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
}

export function createFeedClient(options: FeedClientOptions): FeedClient {
  return new FeedClient(options);
}
