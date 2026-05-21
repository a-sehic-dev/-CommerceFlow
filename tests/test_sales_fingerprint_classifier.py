from app.services.dataset_classifier import classify_headers


def test_sales_file_with_margin_column_classifies_as_sales():
    headers = [
        "order_id",
        "sku",
        "quantity",
        "unit_price",
        "revenue",
        "margin",
        "sales_channel",
        "sold_at",
        "region",
        "discount_amount",
        "customer",
        "currency",
    ]
    result = classify_headers(headers)
    assert result.primary_type == "sales"
    assert not result.needs_confirmation


def test_products_catalog_classifies_as_products():
    headers = ["sku", "title", "category", "price", "cost", "margin", "status"]
    result = classify_headers(headers)
    assert result.primary_type == "products"
    assert not result.needs_confirmation
