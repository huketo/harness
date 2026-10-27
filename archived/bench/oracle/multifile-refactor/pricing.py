def discounted_total(subtotal: float, discount_rate: float) -> float:
    """Apply a fractional discount rate to a subtotal."""
    if not 0 <= discount_rate <= 1:
        raise ValueError("discount_rate must be between 0 and 1")
    return round(subtotal * (1 - discount_rate), 2)
