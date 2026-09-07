import type { IncomingMessage, ServerResponse } from "node:http";
import { NotFoundError, ValidationError } from "./errors";
import type { FileCache } from "./cache";
import { takePage } from "./util/page";

export interface Order {
  readonly id: string;
  readonly customer: string;
  readonly total: number;
}

export interface HandlerDeps {
  readonly cache: FileCache;
  readonly orders: readonly Order[];
}

const DEFAULT_LIMIT = 20;

export function createHandler(deps: HandlerDeps) {
  return async function handle(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const url = new URL(request.url ?? "/", "http://localhost");
    if (url.pathname === "/healthz") {
      send(response, 200, { status: "ok", cached: deps.cache.size });
      return;
    }
    if (url.pathname === "/orders") {
      const offset = readInt(url, "offset", 0);
      const limit = readInt(url, "limit", DEFAULT_LIMIT);
      const page = takePage([...deps.orders], offset, limit);
      send(response, 200, page);
      return;
    }
    throw new NotFoundError(`no route for ${request.method ?? "GET"} ${url.pathname}`);
  };
}

function readInt(url: URL, key: string, fallback: number): number {
  const raw = url.searchParams.get(key);
  if (raw === null) {
    return fallback;
  }
  const value = Number.parseInt(raw, 10);
  if (!Number.isSafeInteger(value)) {
    throw new ValidationError(`${key} must be an integer: ${raw}`);
  }
  return value;
}

function send(response: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
  });
  response.end(payload);
}
