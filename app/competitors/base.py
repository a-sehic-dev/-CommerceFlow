from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CompetitorPriceSnapshot:
    competitor_id: str
    product_url: str
    sku: str | None
    price: float
    in_stock: bool
    captured_at: datetime


class CompetitorTrackerBase(ABC):
    """Base class for future price/stock monitoring integrations."""

    @abstractmethod
    async def fetch_prices(self, urls: list[str]) -> list[CompetitorPriceSnapshot]:
        ...

    @abstractmethod
    async def fetch_stock_status(self, urls: list[str]) -> list[CompetitorPriceSnapshot]:
        ...
