export function totalMilliseconds(request) {
  const requestQueueResidenceTimeMilliseconds = request.queue_ms;
  return requestQueueResidenceTimeMilliseconds + request.service_ms;
}

export function summarize(requests) {
  if (requests.length === 0) throw new Error('At least one request is required');
  const totals = requests.map(totalMilliseconds).sort((a, b) => a - b);
  return {
    count: totals.length,
    mean: totals.reduce((sum, value) => sum + value, 0) / totals.length,
    p95: totals[Math.ceil(totals.length * 0.95) - 1],
  };
}
