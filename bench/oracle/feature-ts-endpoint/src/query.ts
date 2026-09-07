/**
 * Query support for the order collection endpoint: filtering, sorting and
 * pagination of `GET /orders`.
 */

import {
  ORDER_SORT_FIELDS,
  ORDER_STATUSES,
  compareOrders,
  type Order,
  type OrderSortField,
  type OrderStatus,
} from "./orders.ts";

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

const KNOWN_PARAMS: Record<string, true> = {
  status: true,
  customer: true,
  page: true,
  per_page: true,
  sort: true,
};

/** A rejected query: the HTTP layer answers 400 with this message. */
export class OrderQueryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OrderQueryError";
  }
}

export interface OrderQuery {
  status?: OrderStatus;
  /** Lower-cased substring the customer name must contain. */
  customer?: string;
  page: number;
  perPage: number;
  sortField: OrderSortField;
  descending: boolean;
}

function positiveInteger(raw: string, name: string, maximum: number): number {
  if (!/^[0-9]+$/.test(raw)) {
    throw new OrderQueryError(`${name} must be a positive integer`);
  }
  const value = Number(raw);
  if (value < 1 || value > maximum) {
    throw new OrderQueryError(`${name} must be between 1 and ${maximum}`);
  }
  return value;
}

export function parseOrderQuery(params: URLSearchParams): OrderQuery {
  for (const name of params.keys()) {
    if (!Object.hasOwn(KNOWN_PARAMS, name)) {
      throw new OrderQueryError(`unknown query parameter ${name}`);
    }
  }

  const query: OrderQuery = {
    page: 1,
    perPage: DEFAULT_PER_PAGE,
    sortField: "id",
    descending: false,
  };

  const status = params.get("status");
  if (status !== null) {
    const known = ORDER_STATUSES.find((candidate) => candidate === status);
    if (!known) {
      throw new OrderQueryError(`status must be one of ${ORDER_STATUSES.join(", ")}`);
    }
    query.status = known;
  }

  const customer = params.get("customer");
  if (customer !== null) {
    query.customer = customer.toLowerCase();
  }

  const page = params.get("page");
  if (page !== null) {
    query.page = positiveInteger(page, "page", Number.MAX_SAFE_INTEGER);
  }

  const perPage = params.get("per_page");
  if (perPage !== null) {
    query.perPage = positiveInteger(perPage, "per_page", MAX_PER_PAGE);
  }

  const sort = params.get("sort");
  if (sort !== null) {
    const descending = sort.startsWith("-");
    const field = ORDER_SORT_FIELDS.find((candidate) => candidate === (descending ? sort.slice(1) : sort));
    if (!field) {
      throw new OrderQueryError(
        `sort must be one of ${ORDER_SORT_FIELDS.join(", ")}, optionally prefixed with -`,
      );
    }
    query.sortField = field;
    query.descending = descending;
  }

  return query;
}

/** Applies filters, sorting and pagination, in that order. */
export function selectOrders(orders: Order[], query: OrderQuery): OrderCollection {
  const matched = orders.filter((order) => {
    if (query.status && order.status !== query.status) {
      return false;
    }
    return query.customer === undefined || order.customer.toLowerCase().includes(query.customer);
  });

  matched.sort((left, right) => compareOrders(left, right, query.sortField, query.descending));

  const start = (query.page - 1) * query.perPage;
  return {
    orders: matched.slice(start, start + query.perPage),
    total: matched.length,
    page: query.page,
    per_page: query.perPage,
    total_pages: Math.max(1, Math.ceil(matched.length / query.perPage)),
  };
}
