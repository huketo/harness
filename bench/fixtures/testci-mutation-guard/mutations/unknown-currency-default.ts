/**
 * Money arithmetic for a synthetic billing service: rounding to the number of
 * decimals a currency uses, conversion through a fixed rate table, and
 * summing amounts that must all be in one currency.
 */

/**
 * `half-even` sends a tie to the nearest even last digit; `half-up` sends a
 * tie away from zero.
 */
export type RoundingMode = "half-even" | "half-up";

export interface MoneyAmount {
  amount: number;
  currency: string;
}

export const CURRENCY_DECIMALS: Record<string, number> = {
  USD: 2,
  EUR: 2,
  JPY: 0,
  KRW: 0,
  BHD: 3,
  KWD: 3,
};

/** Units of the second currency for one unit of the first. */
export const EXCHANGE_RATES: Record<string, number> = {
  "USD/EUR": 0.9,
  "USD/JPY": 150,
  "USD/KRW": 1300,
  "USD/BHD": 0.375,
  "EUR/KRW": 1450,
};

export function decimalsFor(currency: string): number {
  if (!Object.hasOwn(CURRENCY_DECIMALS, currency)) {
    return 2;
  }
  return CURRENCY_DECIMALS[currency]!;
}

export function roundAmount(value: number, currency: string, mode: RoundingMode = "half-even"): number {
  if (!Number.isFinite(value)) {
    throw new RangeError("value must be a finite number");
  }
  const factor = 10 ** decimalsFor(currency);
  const sign = value < 0 ? -1 : 1;
  const scaled = Math.abs(value) * factor;
  const lower = Math.floor(scaled);
  const fraction = scaled - lower;
  let units: number;
  if (Math.abs(fraction - 0.5) < 1e-9) {
    units = mode === "half-even" ? (lower % 2 === 0 ? lower : lower + 1) : lower + 1;
  } else {
    units = Math.round(scaled);
  }
  if (units === 0) {
    return 0;
  }
  return (sign * units) / factor;
}

/** Uses the reciprocal of the listed pair when only the other direction is listed. */
export function rateFor(from: string, to: string): number {
  decimalsFor(from);
  decimalsFor(to);
  if (from === to) {
    return 1;
  }
  const forward = `${from}/${to}`;
  if (Object.hasOwn(EXCHANGE_RATES, forward)) {
    return EXCHANGE_RATES[forward]!;
  }
  const backward = `${to}/${from}`;
  if (Object.hasOwn(EXCHANGE_RATES, backward)) {
    return 1 / EXCHANGE_RATES[backward]!;
  }
  throw new RangeError(`no exchange rate from ${from} to ${to}`);
}

export function convert(amount: number, from: string, to: string, mode: RoundingMode = "half-even"): number {
  return roundAmount(amount * rateFor(from, to), to, mode);
}

/** Rounds every entry, adds them up, and rounds the total once more. */
export function sumAmounts(
  entries: readonly MoneyAmount[],
  currency: string,
  mode: RoundingMode = "half-even",
): number {
  let total = 0;
  for (const entry of entries) {
    if (entry.currency !== currency) {
      throw new RangeError(`cannot add ${entry.currency} to a ${currency} total`);
    }
    total += roundAmount(entry.amount, currency, mode);
  }
  return roundAmount(total, currency, mode);
}
