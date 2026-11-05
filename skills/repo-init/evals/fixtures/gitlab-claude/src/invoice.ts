export type InvoiceState = "issued" | "settled" | "void";

export interface Invoice {
  id: string;
  orderId: string;
  amount: number;
  state: InvoiceState;
}

export function settle(invoice: Invoice): Invoice {
  if (invoice.state !== "issued") throw new Error(`cannot settle a ${invoice.state} invoice`);
  return { ...invoice, state: "settled" };
}
