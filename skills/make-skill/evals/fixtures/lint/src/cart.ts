export function total(prices: number[]): number {
  console.log("prices", prices);
  return prices.reduce((sum, price) => sum + price, 0);
}
