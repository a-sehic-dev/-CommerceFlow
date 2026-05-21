"""Empty module payloads when analysis has not been generated."""

EMPTY_MODULE_PAYLOADS: dict[str, dict] = {
    "product_intelligence": {
        "summary": {},
        "top_sellers": [],
        "worst_performers": [],
        "fast_rising": [],
        "declining": [],
    },
    "profit_leakage": {
        "total_estimated_leakage": 0,
        "issue_count": 0,
        "critical_count": 0,
        "issues": [],
        "recommendations": [],
    },
    "inventory_risk": {
        "summary": {},
        "alerts": [],
        "reorder_suggestions": [],
    },
    "data_cleaning": {
        "quality_score": None,
        "issues": [],
    },
}
