from pricing import apply_discount


def total_after_discount(line_prices: list[float], discount_amount: float) -> float:
    """Add invoice lines and apply an absolute discount."""
    return apply_discount(sum(line_prices), discount_amount)
