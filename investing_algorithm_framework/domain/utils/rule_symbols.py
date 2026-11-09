def normalize_rule_symbols(
    symbol: str | None,
    symbols: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if symbols is None:
        return (symbol,) if symbol is not None else None
    if symbol is not None:
        raise ValueError("Specify either symbol or symbols, not both")
    if (not isinstance(symbols, (list, tuple)) or not symbols
            or any(not isinstance(item, str) or not item.strip()
                   or item != item.strip() for item in symbols)):
        raise ValueError("symbols must contain non-empty target symbols")
    normalized = tuple(item.upper() for item in symbols)
    if (any("/" in item for item in normalized)
            or len(set(normalized)) != len(normalized)):
        raise ValueError(
            "symbols must contain unique target symbols, not pairs"
        )
    return normalized
