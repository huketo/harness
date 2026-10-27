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

interface OrderRow {
  id: string;
  customer: string;
  city: string;
  status: string;
  total: number;
  created_at: string;
}

/** Either the collection envelope or the error envelope, as sent on the wire. */
interface OrdersBody {
  orders?: OrderRow[];
  total?: number;
  page?: number;
  per_page?: number;
  total_pages?: number;
  error?: string;
}

async function query(search: string): Promise<{ status: number; body: OrdersBody }> {
  const response = await fetch(`${base}/orders${search}`);
  const body: OrdersBody = await response.json();
  return { status: response.status, body };
}

function ids(body: OrdersBody): string[] {
  const { orders } = body;
  if (!Array.isArray(orders)) {
    throw new Error(`the response carries no orders array: ${JSON.stringify(body)}`);
  }
  return orders.map((order) => order.id);
}

describe("status filter", () => {
  test("keeps only the requested status", async () => {
    const { status, body } = await query("?status=paid");
    expect(status).toBe(200);
    expect(body.total).toBe(14);
    expect(ids(body)).toEqual([
      "ORD-1002",
      "ORD-1004",
      "ORD-1007",
      "ORD-1010",
      "ORD-1014",
      "ORD-1016",
      "ORD-1020",
      "ORD-1022",
      "ORD-1024",
      "ORD-1027",
      "ORD-1030",
      "ORD-1034",
      "ORD-1036",
      "ORD-1040",
    ]);
  });

  test("counts a smaller status group", async () => {
    const { body } = await query("?status=cancelled");
    expect(body.total).toBe(6);
    expect(ids(body)).toEqual(["ORD-1005", "ORD-1012", "ORD-1018", "ORD-1025", "ORD-1032", "ORD-1038"]);
  });

  test("rejects a status outside the known set", async () => {
    const { status, body } = await query("?status=refunded");
    expect(status).toBe(400);
    expect(typeof body.error).toBe("string");
    expect((body.error ?? "").length).toBeGreaterThan(0);
  });
});

describe("customer filter", () => {
  test("matches a case-insensitive substring of the customer name", async () => {
    const { status, body } = await query("?customer=ADLER");
    expect(status).toBe(200);
    expect(body.total).toBe(4);
    expect(ids(body)).toEqual(["ORD-1001", "ORD-1011", "ORD-1021", "ORD-1031"]);
  });

  test("matches a first name fragment too", async () => {
    const { body } = await query("?customer=rowan");
    expect(ids(body)).toEqual(["ORD-1001", "ORD-1021"]);
  });

  test("matches a substring that spans the space in the name", async () => {
    const { body } = await query("?customer=Rowan%20Adler");
    expect(body.total).toBe(2);
    expect(ids(body)).toEqual(["ORD-1001", "ORD-1021"]);
  });

  test("answers an empty selection when nobody matches", async () => {
    const { status, body } = await query("?customer=zzz");
    expect(status).toBe(200);
    expect(body.orders).toEqual([]);
    expect(body.total).toBe(0);
    expect(body.total_pages).toBe(1);
  });

  test("combines with the status filter", async () => {
    const { body } = await query("?status=shipped&customer=adler");
    expect(body.total).toBe(2);
    expect(ids(body)).toEqual(["ORD-1011", "ORD-1031"]);
  });
});

describe("pagination", () => {
  test("cuts the selection into pages", async () => {
    const { status, body } = await query("?page=2&per_page=7");
    expect(status).toBe(200);
    expect(body.page).toBe(2);
    expect(body.per_page).toBe(7);
    expect(body.total).toBe(40);
    expect(body.total_pages).toBe(6);
    expect(ids(body)).toEqual([
      "ORD-1008",
      "ORD-1009",
      "ORD-1010",
      "ORD-1011",
      "ORD-1012",
      "ORD-1013",
      "ORD-1014",
    ]);
  });

  test("returns the short last page", async () => {
    const { body } = await query("?page=6&per_page=7");
    expect(ids(body)).toEqual(["ORD-1036", "ORD-1037", "ORD-1038", "ORD-1039", "ORD-1040"]);
    expect(body.total_pages).toBe(6);
  });

  test("answers an empty page past the end without changing the totals", async () => {
    const { status, body } = await query("?page=7&per_page=7");
    expect(status).toBe(200);
    expect(body.orders).toEqual([]);
    expect(body.page).toBe(7);
    expect(body.total).toBe(40);
    expect(body.total_pages).toBe(6);
  });

  test("counts pages of the filtered selection, not of every order", async () => {
    const { body } = await query("?status=cancelled&per_page=4&page=2");
    expect(body.total).toBe(6);
    expect(body.total_pages).toBe(2);
    expect(ids(body)).toEqual(["ORD-1032", "ORD-1038"]);
  });

  test("rejects page and per_page values outside the allowed range", async () => {
    for (const search of ["?page=0", "?page=-1", "?page=abc", "?page=1.5", "?per_page=0", "?per_page=101", "?per_page=x"]) {
      const { status, body } = await query(search);
      expect(status).toBe(400);
      expect(typeof body.error).toBe("string");
    }
  });
});

describe("sorting", () => {
  test("sorts by total ascending", async () => {
    const { status, body } = await query("?sort=total&per_page=5");
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["ORD-1001", "ORD-1003", "ORD-1005", "ORD-1007", "ORD-1030"]);
  });

  test("sorts by total descending and breaks ties by id ascending", async () => {
    const { body } = await query("?sort=-total&per_page=5");
    expect(ids(body)).toEqual(["ORD-1040", "ORD-1038", "ORD-1036", "ORD-1034", "ORD-1032"]);

    const tail = await query("?sort=-total&per_page=5&page=8");
    expect(ids(tail.body)).toEqual(["ORD-1007", "ORD-1030", "ORD-1005", "ORD-1003", "ORD-1001"]);
  });

  test("sorts by creation time, which is not the id order", async () => {
    const ascending = await query("?sort=created_at&per_page=3");
    expect(ids(ascending.body)).toEqual(["ORD-1028", "ORD-1001", "ORD-1029"]);

    const descending = await query("?sort=-created_at&per_page=3");
    expect(ids(descending.body)).toEqual(["ORD-1027", "ORD-1026", "ORD-1025"]);
  });

  test("sorts the filtered selection", async () => {
    const { body } = await query("?status=paid&sort=-total&per_page=3");
    expect(body.total).toBe(14);
    expect(ids(body)).toEqual(["ORD-1040", "ORD-1036", "ORD-1034"]);
  });

  test("keeps id order when no sort is requested", async () => {
    const { body } = await query("?per_page=3");
    expect(ids(body)).toEqual(["ORD-1001", "ORD-1002", "ORD-1003"]);
  });

  test("sorts by id descending", async () => {
    const { status, body } = await query("?sort=-id&per_page=3");
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["ORD-1040", "ORD-1039", "ORD-1038"]);

    const filtered = await query("?status=cancelled&sort=-id");
    expect(ids(filtered.body)).toEqual([
      "ORD-1038",
      "ORD-1032",
      "ORD-1025",
      "ORD-1018",
      "ORD-1012",
      "ORD-1005",
    ]);
  });

  test("rejects an unknown sort key", async () => {
    for (const search of ["?sort=city", "?sort=-city", "?sort=total,id", "?sort="]) {
      const { status, body } = await query(search);
      expect(status).toBe(400);
      expect(typeof body.error).toBe("string");
    }
  });
});

describe("parameter validation", () => {
  test("rejects an unknown query parameter", async () => {
    const { status, body } = await query("?limit=5");
    expect(status).toBe(400);
    expect(typeof body.error).toBe("string");
  });

  test("rejects an inherited property name as a parameter", async () => {
    for (const search of ["?constructor=x", "?toString=x", "?__proto__=x"]) {
      const { status, body } = await query(search);
      expect(status).toBe(400);
      expect(typeof body.error).toBe("string");
    }
  });

  test("still answers the unfiltered collection", async () => {
    const { status, body } = await query("");
    expect(status).toBe(200);
    expect(body.total).toBe(40);
    expect(body.orders).toHaveLength(40);
    expect(body.page).toBe(1);
    expect(body.total_pages).toBe(1);
  });
});
