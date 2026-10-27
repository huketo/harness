def inclusive_span(start: int, end: int) -> int:
    """Return the number of integer positions in the inclusive interval."""
    if not isinstance(start, int) or not isinstance(end, int):
        raise TypeError("start and end must be integers")
    if end < start:
        return 0
    return end - start + 1
