import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import type { AddressInfo } from "node:net";

import { createOrdersServer } from "../src/server.ts";

const server = createOrdersServer();
let base = "";

beforeAll(async () => {
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
  const { port } = server.address() as AddressInfo;
  base = `http://127.0.0.1:${port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
});

describe("order service", () => {
  test("answers the collection with every order in id order", async () => {
    const response = await fetch(`${base}/orders`);
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/json; charset=utf-8");
    const body = await response.json();
    expect(body.total).toBe(40);
    expect(body.orders).toHaveLength(40);
    expect(body.orders[0].id).toBe("ORD-1001");
    expect(body.orders[39].id).toBe("ORD-1040");
  });

  test("every collection entry carries the full record", async () => {
    const body = await (await fetch(`${base}/orders`)).json();
    expect(body.orders[0]).toEqual({
      id: "ORD-1001",
      customer: "Rowan Adler",
      city: "Aldermoor",
      status: "pending",
      total: 48.25,
      created_at: "2026-01-02T06:00:00Z",
    });
    for (const order of body.orders) {
      expect(["pending", "paid", "shipped", "cancelled"]).toContain(order.status);
      expect(typeof order.total).toBe("number");
    }
  });

  test("answers a single order by id", async () => {
    const response = await fetch(`${base}/orders/ORD-1007`);
    expect(response.status).toBe(200);
    const order = await response.json();
    expect(order.customer).toBe("Anwen Ivers");
    expect(order.status).toBe("paid");
    expect(order.total).toBe(70.75);
  });

  test("answers 404 for an unknown id and an unknown route", async () => {
    const missing = await fetch(`${base}/orders/ORD-9999`);
    expect(missing.status).toBe(404);
    expect(typeof (await missing.json()).error).toBe("string");

    const stray = await fetch(`${base}/customers`);
    expect(stray.status).toBe(404);
  });

  test("answers 405 for a write method", async () => {
    const response = await fetch(`${base}/orders`, { method: "POST" });
    expect(response.status).toBe(405);
    expect(typeof (await response.json()).error).toBe("string");
  });
});
