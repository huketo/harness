/** Response shape of the order collection endpoint. */

import type { Order } from "./orders.ts";

export interface OrderCollection {
  orders: Order[];
  /** Number of orders the request selected. */
  total: number;
  /** 1-based page number of `orders` within the selection. */
  page: number;
  /** Page size used to cut `orders` out of the selection. */
  per_page: number;
  /** Number of pages the selection covers, at least 1. */
  total_pages: number;
}

export const DEFAULT_PER_PAGE = 50;
export const MAX_PER_PAGE = 100;
