import { watch } from "node:fs/promises";
import type { FileCache } from "./cache";

export interface WatchOptions {
  readonly root: string;
  readonly signal: AbortSignal;
}

export class CacheWatcher {
  private readonly cache: FileCache;
  private seen = 0;

  constructor(cache: FileCache) {
    this.cache = cache;
  }

  get changeCount(): number {
    return this.seen;
  }

  async run(options: WatchOptions): Promise<void> {
    const events = watch(options.root, { signal: options.signal });
    for await (const event of events) {
      if (event.filename === null) {
        continue;
      }
      this.seen += 1;
      this.cache.invalidate(`${options.root}/${event.filename}`);
    }
  }
}
