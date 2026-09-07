const MILLIS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;

export function seconds(count: number): number {
  return Math.round(count * MILLIS_PER_SECOND);
}

export function minutes(count: number): number {
  return seconds(count * SECONDS_PER_MINUTE);
}

export function monotonicNow(): number {
  return Number(process.hrtime.bigint() / 1000000n);
}

export function isExpired(stampedAt: number, ttl: number, now: number): boolean {
  return now - stampedAt >= ttl;
}
