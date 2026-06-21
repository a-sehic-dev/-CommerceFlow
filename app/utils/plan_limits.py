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
    }
