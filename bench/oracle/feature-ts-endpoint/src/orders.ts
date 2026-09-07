/** Order records, the lookups the HTTP layer needs, and their ordering. */

import { ORDERS } from "./data.ts";

export const ORDER_STATUSES = ["pending", "paid", "shipped", "cancelled"] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const ORDER_SORT_FIELDS = ["id", "total", "created_at"] as const;

export type OrderSortField = (typeof ORDER_SORT_FIELDS)[number];

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

/**
 * Total order on records: by `field` in the requested direction, with equal
 * values resolved by ascending id so that either direction is deterministic.
 */
export function compareOrders(
  left: Order,
  right: Order,
  field: OrderSortField,
  descending: boolean,
): number {
  const primary = field === "total" ? left.total - right.total : left[field].localeCompare(right[field]);
  if (primary !== 0) {
    return descending ? -primary : primary;
  }
  return left.id.localeCompare(right.id);
}
