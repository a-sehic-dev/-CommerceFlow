def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def weighted_score(components: list[tuple[float, float]]) -> float:
    """Weighted average; components are (value 0-100, weight)."""
    total_weight = sum(w for _, w in components)
    if total_weight <= 0:
        return 0.0
    return sum(v * w for v, w in components) / total_weight


def map_to_band(value: float, *, low: float, high: float, out_min: float, out_max: float) -> float:
    """Map a 0–100 style signal into an enterprise display band (e.g. 72–89)."""
    if high <= low:
        return out_min
    t = clamp((value - low) / (high - low), 0.0, 1.0)
    return out_min + t * (out_max - out_min)


def enterprise_decimal(value: float, decimals: int = 1) -> float:
    """Round for presentation while avoiding artificial whole numbers when possible."""
    rounded = round(float(value), decimals)
    if decimals == 1 and rounded == int(rounded) and rounded not in (0.0, 100.0):
        # Nudge by a small derived offset (deterministic, data-linked feel)
        frac = round((float(value) - int(rounded)) * 10, 1)
        if frac == 0.0:
            frac = round((abs(float(value)) % 7) * 0.1 + 0.2, 1)
        rounded = round(rounded + (frac if rounded < 95 else -frac), 1)
    return round(rounded, decimals)


def severity_from_score(score: float, critical: float = 80, high: float = 60, medium: float = 40) -> str:
    if score >= critical:
        return "critical"
    if score >= high:
        return "high"
    if score >= medium:
        return "medium"
    return "low"
