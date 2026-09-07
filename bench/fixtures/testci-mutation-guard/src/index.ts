/**
 * Demo entry point: `bun run src/index.ts`.
 *
 * Prints an invoice total in three currencies so the module can be exercised
 * by hand.
 */

import { convert, roundAmount, sumAmounts, type MoneyAmount } from "./money.ts";

const lines: MoneyAmount[] = [
  { amount: 12.345, currency: "USD" },
  { amount: 7.005, currency: "USD" },
  { amount: 99.994, currency: "USD" },
];
const subtotalUsd = sumAmounts(lines, "USD");

console.log(`USD subtotal: ${subtotalUsd}`);
console.log(`USD subtotal, half-up: ${sumAmounts(lines, "USD", "half-up")}`);
console.log(`KRW total: ${convert(subtotalUsd, "USD", "KRW")}`);
console.log(`EUR total: ${convert(subtotalUsd, "USD", "EUR")}`);
console.log(`EUR back to USD: ${convert(roundAmount(9.5, "EUR"), "EUR", "USD")}`);
