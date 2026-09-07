/** Order records and the lookups the HTTP layer needs. */

import { ORDERS } from "./data.ts";

export const ORDER_STATUSES = ["pending", "paid", "shipped", "cancelled"] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];

export interface Order {
  id: string;
  customer: string;
  city: string;
  status: OrderStatus;
  /** Amount in whole currency units, rounded to two decimals. */
  total: number;
  /** RFC 3339 timestamp in UTC. */
  created_at: string;
}

export function listOrders(): Order[] {
  return [...ORDERS].sort((left, right) => left.id.localeCompare(right.id));
}

export function findOrder(id: string): Order | undefined {
  return ORDERS.find((order) => order.id === id);
}
