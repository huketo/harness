def apply_discount(amount: float, discount_amount: float) -> float:
    """Apply an absolute discount amount to a subtotal."""
    return round(amount - discount_amount, 2)
