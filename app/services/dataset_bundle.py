"""Typed container for analytics datasets — avoids brittle tuple unpacking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class DatasetBundle:
    products: pd.DataFrame = field(default_factory=pd.DataFrame)
    sales: pd.DataFrame = field(default_factory=pd.DataFrame)
    inventory: pd.DataFrame = field(default_factory=pd.DataFrame)
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def row_counts(self) -> dict[str, int]:
        return self.info.get("row_counts", {})

    @property
    def selection(self) -> dict[str, int | None]:
        return self.info.get("selection", {})

    def get(self, name: str) -> pd.DataFrame:
        return getattr(self, name, pd.DataFrame())

    def empty(self) -> bool:
        return (
            self.products.empty
            and self.sales.empty
            and self.inventory.empty
        )
