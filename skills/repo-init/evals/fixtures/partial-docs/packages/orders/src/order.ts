export interface Order {
  id: string;
  lines: { sku: string; quantity: number }[];
  placedAt: Date;
}
