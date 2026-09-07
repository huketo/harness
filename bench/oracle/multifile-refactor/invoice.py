from pricing import discounted_total


def invoice_total(line_prices: list[float], discount_rate: float) -> float:
    """Add invoice lines and apply a fractional discount rate."""
    return discounted_total(sum(line_prices), discount_rate)
