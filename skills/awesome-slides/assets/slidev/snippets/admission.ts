export function admit(
  queueDepth: number, limit: number,
) {
  if (queueDepth >= limit)
    return {
      accepted: false, retryAfterMs: 1000,
    }
  return { accepted: true }
}
