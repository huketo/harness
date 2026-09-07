import { createServer } from "node:http";
import { AppError } from "./errors";
import { FileCache } from "./cache";
import { createHandler, type Order } from "./handler";
import { TaskQueue } from "./queue";
import { CacheWatcher } from "./watcher";
import { minutes } from "./util/time";

const PORT = 8080;
const CACHE_TTL = minutes(5);

export interface ServerHandle {
  close(): void;
}

export function start(orders: Order[], root: string): ServerHandle {
  const cache = new FileCache(CACHE_TTL);
  const queue = new TaskQueue();
  const watcher = new CacheWatcher(cache);
  const controller = new AbortController();
  const handle = createHandler({ cache, orders });
  const server = createServer((request, response) => {
    handle(request, response).catch((error: unknown) => {
      const status = error instanceof AppError ? statusFor(error) : 500;
      response.writeHead(status, { "content-type": "application/json; charset=utf-8" });
      response.end(JSON.stringify({ error: describe(error) }));
    });
  });
  queue.push("warmup", async () => {
    await cache.read(`${root}/index.txt`);
  });
  void queue.drain().catch((error: unknown) => {
    console.error("warmup failed", describe(error));
  });
  void watcher.run({ root, signal: controller.signal }).catch((error: unknown) => {
    console.error("watcher stopped", describe(error));
  });
  server.listen(PORT);
  return {
    close(): void {
      controller.abort();
      server.close();
    },
  };
}

function statusFor(error: AppError): number {
  if (error.code === "NOT_FOUND") {
    return 404;
  }
  if (error.code === "VALIDATION") {
    return 400;
  }
  if (error.code === "TIMEOUT") {
    return 504;
  }
  return 500;
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
