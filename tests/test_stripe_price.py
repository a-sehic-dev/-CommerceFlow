import pytest

from app.utils.stripe_price import validate_stripe_price_id


def test_rejects_product_id():
    with pytest.raises(ValueError, match="price_"):
        validate_stripe_price_id("prod_UykSew2VS8IWr", plan_label="pro")


def test_accepts_price_id():
    assert validate_stripe_price_id("price_1ABC123", plan_label="pro") == "price_1ABC123"
