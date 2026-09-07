import { ValidationError } from "../errors";

export interface Page<T> {
  items: T[];
  offset: number;
  total: number;
  hasMore: boolean;
}

export function takePage<T>(items: T[], offset: number, limit: number): Page<T> {
  if (offset < 0) {
    throw new ValidationError(`offset must not be negative: ${offset}`);
  }
  if (limit <= 0) {
    throw new ValidationError(`limit must be positive: ${limit}`);
  }
  const end = Math.min(offset + limit, items.length);
  return {
    items: items.slice(offset, end),
    offset,
    total: items.length,
    hasMore: end < items.length,
  };
}
