"""Enterprise KPI calibration tests."""

import pandas as pd

from app.services.metrics_engine import MetricsEngine


def _rich_analysis():
    return {
        "inventory_risk": {
            "summary": {
                "avg_health_score": 61.2,
                "low_stock_count": 42,
                "overstock_count": 18,
                "dead_inventory_count": 87,
                "dead_inventory_value": 1_155_629.27,
            },
            "alerts": [
                {"type": "stockout_risk", "severity": "critical"},
                {"type": "stockout_risk", "severity": "high"},
                {"type": "dead_inventory", "severity": "critical"},
            ],
        },
        "profit_leakage": {
            "issues": [
                {"type": "low_margin", "severity": "high"},
                {"type": "low_margin", "severity": "critical"},
            ],
            "total_estimated_leakage": 357_653.81,
            "critical_count": 3,
            "issue_count": 12,
        },
        "data_cleaning": {"quality_score": 88},
    }


def test_operational_risk_in_realistic_band():
    inv = pd.DataFrame(
        {
            "sku": [f"SKU{i}" for i in range(920)],
            "quantity_on_hand": [10] * 920,
            "days_in_stock": [45] * 920,
        }
    )
    sales = pd.DataFrame({"sku": ["SKU1"], "revenue": [100.0], "quantity": [5]})
    selection = {
        "products_import_id": 1,
        "sales_import_id": 2,
        "inventory_import_id": 3,
    }
    risk, _ = MetricsEngine._operational_risk(_rich_analysis(), selection, 2_384_358.71, inv)
    assert risk is not None
    assert 72.0 <= risk <= 89.0
    assert risk != 100.0


def test_inventory_efficiency_in_realistic_band():
    inv = pd.DataFrame(
        {
            "sku": [f"SKU{i}" for i in range(200)],
            "quantity_on_hand": [25] * 200,
            "days_in_stock": [40] * 200,
        }
    )
    sales = pd.DataFrame(
        {
            "sku": [f"SKU{i % 200}" for i in range(500)],
            "quantity": [2] * 500,
            "revenue": [50.0] * 500,
        }
    )
    selection = {"inventory_import_id": 1, "sales_import_id": 2}
    eff, _ = MetricsEngine._inventory_efficiency(inv, sales, _rich_analysis(), selection)
    assert eff is not None
    assert 68.0 <= eff <= 86.0


def test_profit_leakage_always_positive():
    selection = {"sales_import_id": 1}
    val, _ = MetricsEngine._profit_leakage(_rich_analysis(), selection, 1_000_000.0)
    assert val is not None
    assert val >= 0
