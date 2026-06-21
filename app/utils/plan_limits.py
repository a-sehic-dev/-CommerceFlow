"""Plan tiers and feature limits (Faza 4 billing)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanLimits:
    slug: str
    label: str
    price_hint: str
    max_seats: int
    max_stores: int
    live_sync: bool
    team_invites: bool
    weekly_email: bool
    pdf_export: bool
    summary: str


PLAN_LIMITS: dict[str, PlanLimits] = {
    "starter": PlanLimits(
        slug="starter",
        label="Starter",
        price_hint="Free",
        max_seats=1,
        max_stores=0,
        live_sync=False,
        team_invites=False,
        weekly_email=False,
        pdf_export=False,
        summary="CSV upload, analysis, Excel export",
    ),
    "pro": PlanLimits(
        slug="pro",
        label="Pro",
        price_hint="$29/mo",
        max_seats=2,
        max_stores=1,
        live_sync=True,
        team_invites=False,
        weekly_email=True,
        pdf_export=True,
        summary="1 live store, PDF + weekly email, 2 seats",
    ),
    "team": PlanLimits(
        slug="team",
        label="Team",
        price_hint="$79/mo",
        max_seats=5,
        max_stores=1,
        live_sync=True,
        team_invites=True,
        weekly_email=True,
        pdf_export=True,
        summary="Team invites & roles, 1 store, 5 seats",
    ),
    "ultra": PlanLimits(
        slug="ultra",
        label="Ultra",
        price_hint="$129/mo",
        max_seats=10,
        max_stores=3,
        live_sync=True,
        team_invites=True,
        weekly_email=True,
        pdf_export=True,
        summary="Up to 3 stores, 10 seats, multi-brand",
    ),
}


def normalize_plan(plan: str | None) -> str:
    slug = (plan or "starter").strip().lower()
    return slug if slug in PLAN_LIMITS else "starter"


def get_plan_limits(plan: str | None) -> PlanLimits:
    return PLAN_LIMITS[normalize_plan(plan)]


PLAN_RANK = {"starter": 0, "pro": 1, "team": 2, "ultra": 3}


def plan_rank(plan: str | None) -> int:
    return PLAN_RANK.get(normalize_plan(plan), 0)


def plan_features_list(plan: str | None) -> list[str]:
    limits = get_plan_limits(plan)
    features = [
        "CSV & Excel upload with full analysis dashboard",
        f"Up to {limits.max_seats} workspace seat{'s' if limits.max_seats != 1 else ''}",
    ]
    if limits.max_stores:
        features.append(
            f"Up to {limits.max_stores} live store{'s' if limits.max_stores != 1 else ''} (Shopify / WooCommerce)"
        )
    else:
        features.append("Manual CSV/Excel imports (no live store sync)")
    if limits.live_sync:
        features.append("Automated Shopify & WooCommerce sync")
    if limits.pdf_export:
        features.append("Executive PDF export")
    if limits.weekly_email:
        features.append("Scheduled weekly Excel report by email")
    if limits.team_invites:
        features.append("Team invites with Owner / Analyst / Viewer roles")
    if limits.slug == "ultra":
        features.append("Multi-brand / multi-store operations in one workspace")
    return features


def plan_limits_payload(plan: str | None) -> dict:
    limits = get_plan_limits(plan)
    return {
        "slug": limits.slug,
        "label": limits.label,
        "price_hint": limits.price_hint,
        "max_seats": limits.max_seats,
        "max_stores": limits.max_stores,
        "live_sync": limits.live_sync,
        "team_invites": limits.team_invites,
        "weekly_email": limits.weekly_email,
        "pdf_export": limits.pdf_export,
        "summary": limits.summary,
        "features": plan_features_list(plan),
    }
