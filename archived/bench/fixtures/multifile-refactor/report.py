from invoice import total_after_discount


def render_summary(line_prices: list[float], discount_amount: float) -> str:
    total = total_after_discount(line_prices, discount_amount)
    return f"Total: ${total:.2f}"
