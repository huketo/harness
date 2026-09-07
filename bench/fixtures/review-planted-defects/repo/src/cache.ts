import { readFile } from "node:fs/promises";
import { NotFoundError } from "./errors";
import { isExpired, minutes, monotonicNow } from "./util/time";

interface Entry {
  readonly text: string;
  readonly stampedAt: number;
}

const DEFAULT_TTL = minutes(5);

export class FileCache {
  private readonly entries = new Map<string, Entry>();
  private readonly ttl: number;
  private hits = 0;

  constructor(ttl: number = DEFAULT_TTL) {
    this.ttl = ttl;
  }

  get size(): number {
    return this.entries.size;
  }

  get hitCount(): number {
    return this.hits;
  }

  async read(path: string): Promise<string> {
    const cached = this.entries.get(path);
    if (cached !== undefined && !isExpired(cached.stampedAt, this.ttl, monotonicNow())) {
      this.hits += 1;
      return cached.text;
    }
    const text = await this.load(path);
    this.entries.set(path, { text, stampedAt: monotonicNow() });
    return text;
  }

  invalidate(path: string): void {
    this.entries.delete(path);
  }

  private async load(path: string): Promise<string> {
    try {
      return await readFile(path, "utf8");
    } catch {
      throw new NotFoundError(`cannot read ${path}`);
    }
  }
}
