from app.services.dataset_classifier import classify_headers


def test_sales_detection():
    r = classify_headers(["order_id", "revenue", "quantity", "sold_at", "customer", "sales_channel"])
    assert r.primary_type == "sales"
    assert r.confidence >= 0.5
    assert not r.needs_confirmation


def test_products_detection():
    r = classify_headers(["product_name", "sku", "category", "unit_price", "margin", "status"])
    assert r.primary_type == "products"
    assert not r.needs_confirmation


def test_inventory_detection():
    r = classify_headers(["warehouse", "on_hand", "available_units", "reserved", "inbound", "stock"])
    assert r.primary_type == "inventory"
    assert not r.needs_confirmation


def test_low_confidence():
    r = classify_headers(["column_a", "column_b"])
    assert r.needs_confirmation
    assert r.primary_type == "unknown"
