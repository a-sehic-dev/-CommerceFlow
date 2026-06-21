"""Stripe price id validation for billing checkout."""


def validate_stripe_price_id(price_id: str | None, *, plan_label: str) -> str:
    value = (price_id or "").strip()
    if not value:
        raise ValueError(f"Stripe price id is not configured for {plan_label}.")
    if value.startswith("prod_"):
        raise ValueError(
            f"STRIPE_PRICE_{plan_label.upper()} must be a Price id (price_...), not a Product id (prod_...). "
            "In Stripe: open the product → Pricing → copy Price ID."
        )
    if not value.startswith("price_"):
        raise ValueError(
            f"STRIPE_PRICE_{plan_label.upper()} must start with price_. "
            "In Stripe: Product catalog → product → Pricing → copy Price ID."
        )
    return value
