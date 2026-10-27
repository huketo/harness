import { describe, expect, test } from "bun:test";

import {
  convert,
  decimalsFor,
  rateFor,
  roundAmount,
  sumAmounts,
} from "../src/money.ts";

describe("decimalsFor", () => {
  test("reports the decimals each currency is billed in", () => {
    expect(decimalsFor("USD")).toBe(2);
    expect(decimalsFor("EUR")).toBe(2);
    expect(decimalsFor("JPY")).toBe(0);
    expect(decimalsFor("KRW")).toBe(0);
    expect(decimalsFor("BHD")).toBe(3);
    expect(decimalsFor("KWD")).toBe(3);
  });

  test("rejects an unknown currency instead of assuming a default", () => {
    expect(() => decimalsFor("XYZ")).toThrow(RangeError);
    expect(() => decimalsFor("")).toThrow(RangeError);
  });

  test("rejects an inherited property name", () => {
    expect(() => decimalsFor("toString")).toThrow(RangeError);
    expect(() => decimalsFor("constructor")).toThrow(RangeError);
  });
});

describe("roundAmount", () => {
  test("keeps amounts that already fit the currency", () => {
    expect(roundAmount(12.34, "USD")).toBe(12.34);
    expect(roundAmount(7, "JPY")).toBe(7);
    expect(roundAmount(1.234, "BHD")).toBe(1.234);
  });

  test("rounds a non-tie to the nearer value under either mode", () => {
    expect(roundAmount(99.994, "USD")).toBe(99.99);
    expect(roundAmount(99.996, "USD")).toBe(100);
    expect(roundAmount(1234.56, "KRW")).toBe(1235);
    expect(roundAmount(1234.44, "KRW", "half-up")).toBe(1234);
  });

  test("sends a tie to the nearest even digit in half-even mode", () => {
    expect(roundAmount(2.345, "USD")).toBe(2.34);
    expect(roundAmount(2.355, "USD")).toBe(2.36);
    expect(roundAmount(0.5, "KRW")).toBe(0);
    expect(roundAmount(1.5, "KRW")).toBe(2);
    expect(roundAmount(1.2345, "BHD")).toBe(1.234);
  });

  test("sends a tie away from zero in half-up mode", () => {
    expect(roundAmount(2.345, "USD", "half-up")).toBe(2.35);
    expect(roundAmount(0.5, "KRW", "half-up")).toBe(1);
    expect(roundAmount(1.2345, "BHD", "half-up")).toBe(1.235);
  });

  test("treats negative amounts symmetrically", () => {
    expect(roundAmount(-2.345, "USD")).toBe(-2.34);
    expect(roundAmount(-2.345, "USD", "half-up")).toBe(-2.35);
    expect(roundAmount(-0.5, "KRW")).toBe(0);
    expect(roundAmount(-1.5, "KRW")).toBe(-2);
    expect(roundAmount(-1.5, "KRW", "half-up")).toBe(-2);
    expect(roundAmount(-2.5, "KRW", "half-up")).toBe(-3);
    expect(roundAmount(-1.2345, "BHD", "half-up")).toBe(-1.235);
  });

  test("returns zero without a sign", () => {
    expect(roundAmount(0, "USD")).toBe(0);
    expect(roundAmount(-0.004, "USD")).toBe(0);
    expect(roundAmount(-0.4, "KRW", "half-up")).toBe(0);
  });

  test("rejects a non-finite amount and an unknown currency", () => {
    expect(() => roundAmount(Number.NaN, "USD")).toThrow(RangeError);
    expect(() => roundAmount(Number.POSITIVE_INFINITY, "USD")).toThrow(RangeError);
    expect(() => roundAmount(1, "XYZ")).toThrow(RangeError);
  });
});

describe("rateFor", () => {
  test("reads a listed pair in its listed direction", () => {
    expect(rateFor("USD", "EUR")).toBe(0.9);
    expect(rateFor("USD", "KRW")).toBe(1300);
    expect(rateFor("USD", "JPY")).toBe(150);
    expect(rateFor("EUR", "KRW")).toBe(1450);
  });

  test("uses the reciprocal for the missing direction", () => {
    expect(rateFor("EUR", "USD")).toBeCloseTo(1 / 0.9, 10);
    expect(rateFor("KRW", "USD")).toBeCloseTo(1 / 1300, 10);
  });

  test("is 1 between a currency and itself", () => {
    expect(rateFor("USD", "USD")).toBe(1);
    expect(rateFor("KRW", "KRW")).toBe(1);
  });

  test("rejects an unlisted pair and an unknown currency", () => {
    expect(() => rateFor("USD", "KWD")).toThrow(RangeError);
    expect(() => rateFor("JPY", "KRW")).toThrow(RangeError);
    expect(() => rateFor("USD", "XYZ")).toThrow(RangeError);
  });
});

describe("convert", () => {
  test("multiplies by the listed rate and rounds to the target currency", () => {
    expect(convert(100, "USD", "KRW")).toBe(130000);
    expect(convert(20, "USD", "EUR")).toBe(18);
    expect(convert(2, "USD", "JPY")).toBe(300);
    expect(convert(10, "USD", "BHD")).toBe(3.75);
  });

  test("rounds the converted amount to the decimals of the target currency", () => {
    expect(convert(3.333, "USD", "KRW")).toBe(4333);
    expect(convert(0.777, "USD", "JPY")).toBe(117);
    expect(convert(1.1111, "USD", "BHD")).toBe(0.417);
  });

  test("converts back through the reciprocal rate", () => {
    expect(convert(1300, "KRW", "USD")).toBe(1);
    expect(convert(9, "EUR", "USD")).toBe(10);
  });

  test("keeps zero at zero and honours the rounding mode", () => {
    expect(convert(0, "USD", "JPY")).toBe(0);
    expect(convert(0.005, "USD", "USD")).toBe(0);
    expect(convert(0.005, "USD", "USD", "half-up")).toBe(0.01);
  });
});

describe("sumAmounts", () => {
  test("rounds each amount before adding them up", () => {
    const lines = [
      { amount: 12.345, currency: "USD" },
      { amount: 7.005, currency: "USD" },
      { amount: 99.994, currency: "USD" },
    ];
    expect(sumAmounts(lines, "USD")).toBe(119.33);
    expect(sumAmounts(lines, "USD", "half-up")).toBe(119.35);
  });

  test("adds whole-unit currencies without decimals", () => {
    const lines = [
      { amount: 1200.4, currency: "KRW" },
      { amount: 800.5, currency: "KRW" },
      { amount: 0.5, currency: "KRW" },
    ];
    expect(sumAmounts(lines, "KRW")).toBe(2000);
    expect(sumAmounts(lines, "KRW", "half-up")).toBe(2002);
  });

  test("adds negative entries", () => {
    const lines = [
      { amount: 100.5, currency: "KRW" },
      { amount: -0.5, currency: "KRW" },
      { amount: -50.5, currency: "KRW" },
    ];
    expect(sumAmounts(lines, "KRW")).toBe(50);
  });

  test("rejects an entry in another currency", () => {
    const mixed = [
      { amount: 10, currency: "USD" },
      { amount: 10, currency: "EUR" },
    ];
    expect(() => sumAmounts(mixed, "USD")).toThrow(RangeError);
    expect(() => sumAmounts(mixed, "EUR")).toThrow(RangeError);
    expect(() => sumAmounts([{ amount: 1, currency: "KRW" }], "JPY")).toThrow(RangeError);
  });

  test("is zero for an empty list", () => {
    expect(sumAmounts([], "USD")).toBe(0);
    expect(sumAmounts([], "KRW")).toBe(0);
  });

  test("rejects an unknown currency", () => {
    expect(() => sumAmounts([{ amount: 1, currency: "XYZ" }], "XYZ")).toThrow(RangeError);
    expect(() => sumAmounts([], "XYZ")).toThrow(RangeError);
  });
});
