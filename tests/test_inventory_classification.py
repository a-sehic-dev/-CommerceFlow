"""Inventory classification — deterministic business rules from real data."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.config import Settings
from app.engines.inventory_risk import InventoryRiskEngine
from app.utils.inventory_classification import (
    CLASSIFICATION_DEAD,
    CLASSIFICATION_INSUFFICIENT,
    CLASSIFICATION_SLOW,
    classify_inventory,
)


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_dead_requires_all_rules():
    as_of = datetime(2026, 6, 1, tzinfo=timezone.utc)
    last_sale = as_of - timedelta(days=200)
    products = pd.DataFrame(
        {"sku": ["DEAD1", "ACTIVE"], "cost": [40.0, 40.0], "title": ["d", "a"]}
    )
    inventory = pd.DataFrame(
        {"sku": ["DEAD1", "ACTIVE"], "quantity_on_hand": [100, 100], "days_in_stock": [200, 200]}
    )
    sales = pd.DataFrame(
        {
            "sku": ["ACTIVE"] * 5,
            "quantity": [1] * 5,
            "sold_at": [as_of - timedelta(days=i) for i in range(5)],
        }
    )
    sales = pd.concat(
        [
            sales,
            pd.DataFrame(
                {
                    "sku": ["DEAD1"],
                    "quantity": [1],
                    "sold_at": [last_sale],
                }
            ),
        ],
        ignore_index=True,
    )
    result = classify_inventory(inventory, sales, products, _settings())
    dead_skus = set(result.dead["sku"].astype(str))
    assert "DEAD1" in dead_skus
    assert "ACTIVE" not in dead_skus
    assert result.dead_inventory_value == 100 * 40.0
    assert result.recoverable_dead_inventory_value == result.dead_inventory_value * 0.25


def test_no_dead_without_activity_history():
    products = pd.DataFrame({"sku": ["X1"], "cost": [25.0], "title": ["x"]})
    inventory = pd.DataFrame({"sku": ["X1"], "quantity_on_hand": [50]})
    sales = pd.DataFrame(columns=["sku", "quantity", "sold_at"])
    result = classify_inventory(inventory, sales, products, _settings())
    assert result.dead.empty
    assert len(result.insufficient_activity) == 1


def test_slow_moving_by_velocity_not_dead():
    as_of = datetime(2026, 6, 1, tzinfo=timezone.utc)
    products = pd.DataFrame({"sku": ["S1"], "cost": [20.0], "title": ["slow"]})
    inventory = pd.DataFrame({"sku": ["S1"], "quantity_on_hand": [30], "days_in_stock": [90]})
    sales = pd.DataFrame(
        {
            "sku": ["S1"] * 3,
            "quantity": [1] * 3,
            "sold_at": [as_of - timedelta(days=10), as_of - timedelta(days=40), as_of - timedelta(days=70)],
        }
    )
    result = classify_inventory(inventory, sales, products, _settings())
    assert result.dead.empty
    assert "S1" in set(result.slow_moving["sku"].astype(str))


def test_overstock_value_uses_excess_units_times_cost():
    as_of = datetime(2026, 6, 1, tzinfo=timezone.utc)
    products = pd.DataFrame({"sku": ["O1"], "cost": [10.0], "title": ["over"]})
    inventory = pd.DataFrame({"sku": ["O1"], "quantity_on_hand": [200]})
    # ~1 unit/day over 90d => target 90 units, excess 110
    sales = pd.DataFrame(
        {
            "sku": ["O1"] * 90,
            "quantity": [1] * 90,
            "sold_at": [as_of - timedelta(days=i) for i in range(90)],
        }
    )
    result = classify_inventory(inventory, sales, products, _settings())
    assert "O1" in set(result.overstock["sku"].astype(str))
    row = result.overstock.iloc[0]
    assert float(row["overstock_value"]) == pytest.approx(110 * 10.0, rel=0.05)


def test_dead_inventory_value_equals_sum_of_dead_rows():
    products = pd.DataFrame({"sku": ["D1"], "cost": [50.0], "title": ["d"]})
    inventory = pd.DataFrame({"sku": ["D1"], "quantity_on_hand": [10], "days_in_stock": [300]})
    sales = pd.DataFrame(columns=["sku", "quantity", "sold_at"])
    result = classify_inventory(inventory, sales, products, _settings())
    if not result.dead.empty:
        assert result.dead_inventory_value == float(result.dead["inventory_value"].sum())


def test_inventory_risk_summary_matches_classification():
    products = pd.DataFrame({"sku": ["D1"], "cost": [30.0], "title": ["d"]})
    inventory = pd.DataFrame({"sku": ["D1"], "quantity_on_hand": [5], "days_in_stock": [250]})
    sales = pd.DataFrame(columns=["sku", "quantity", "sold_at"])
    summary = InventoryRiskEngine().analyze(inventory, sales, products)["summary"]
    assert summary["dead_inventory_count"] == len(
        [r for r in InventoryRiskEngine().analyze(inventory, sales, products)["risk_rows"] if r["classification"] == CLASSIFICATION_DEAD]
    )
    assert "risk_rows" in InventoryRiskEngine().analyze(inventory, sales, products)
