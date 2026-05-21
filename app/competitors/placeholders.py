"""Placeholder implementations — wire real scrapers/APIs in future releases."""

from app.competitors.base import CompetitorPriceSnapshot, CompetitorTrackerBase


class StubCompetitorTracker(CompetitorTrackerBase):
    async def fetch_prices(self, urls: list[str]) -> list[CompetitorPriceSnapshot]:
        return []

    async def fetch_stock_status(self, urls: list[str]) -> list[CompetitorPriceSnapshot]:
        return []
