/** HTTP surface of the demo order service, built on node:http alone. */

import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";

import { findOrder, listOrders } from "./orders.ts";
import { DEFAULT_PER_PAGE, type OrderCollection } from "./query.ts";

function sendJson(response: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
  });
  response.end(payload);
}

function collection(): OrderCollection {
  const orders = listOrders();
  return {
    orders,
    total: orders.length,
    page: 1,
    per_page: DEFAULT_PER_PAGE,
    total_pages: 1,
  };
}

function handle(request: IncomingMessage, response: ServerResponse): void {
  const url = new URL(request.url ?? "/", "http://orders.invalid");
  if (request.method !== "GET") {
    sendJson(response, 405, { error: `method ${request.method} is not allowed` });
    return;
  }
  if (url.pathname === "/orders") {
    sendJson(response, 200, collection());
    return;
  }
  const single = /^\/orders\/([^/]+)$/.exec(url.pathname);
  if (single) {
    const order = findOrder(decodeURIComponent(single[1]!));
    if (!order) {
      sendJson(response, 404, { error: `no order with id ${single[1]}` });
      return;
    }
    sendJson(response, 200, order);
    return;
  }
  sendJson(response, 404, { error: `no route for ${url.pathname}` });
}

/** A server that is not listening yet; the caller picks the port. */
export function createOrdersServer(): Server {
  return createServer(handle);
}
