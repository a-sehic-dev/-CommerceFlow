"""Detection must not depend on filenames — only column structure."""

from app.services.dataset_classifier import classify_dataset, classify_headers
from app.utils.dataset_display import humanize_filename, resolve_display_name


def test_enterprise_sales_headers_not_filename():
    headers = [
        "transaction_id",
        "transaction_date",
        "item_sku",
        "net_sales",
        "ordered_qty",
        "customer_email",
        "sales_channel",
    ]
    result = classify_dataset(headers)
    assert result.primary_type == "sales"
    assert not result.needs_confirmation
    assert "filename" not in result.reason.lower()


def test_warehouse_inventory_headers():
    headers = [
        "item_sku",
        "fulfillment_center",
        "stock_level",
        "qty_available",
        "quantity_reserved",
        "days_in_stock",
    ]
    result = classify_headers(headers)
    assert result.primary_type == "inventory"
    assert result.reason


def test_display_name_does_not_require_sales_in_filename():
    name = resolve_display_name("enterprise_sales_q1.xlsx.xlsx")
    assert "enterprise" in name.lower() or "Enterprise" in name
    assert humanize_filename("warehouse_stock_report.xlsx.xlsx") == "Warehouse Stock Report"


def test_user_override_skips_confirmation():
    headers = ["column_a", "column_b"]
    result = classify_dataset(headers, declared_type="products")
    assert result.primary_type == "products"
    assert not result.needs_confirmation
    assert result.method == "user_override"
