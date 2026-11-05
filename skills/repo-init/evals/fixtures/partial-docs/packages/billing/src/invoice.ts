import type { Order } from "@shopfront/orders/src/order";

export interface Invoice {
  orderId: Order["id"];
  total: number;
}
