from invoice import invoice_total


def render_invoice(line_prices: list[float], discount_rate: float) -> str:
    total = invoice_total(line_prices, discount_rate)
    return f"Invoice total: ${total:.2f}"
