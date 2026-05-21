"""Memory-safe dataframe helpers for enterprise-scale datasets."""

from __future__ import annotations

import sys
from typing import Any, Iterator

import pandas as pd


def memory_mb() -> float:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux: KB, macOS: bytes
        if sys.platform == "darwin":
            return usage / (1024 * 1024)
        return usage / 1024
    except Exception:
        return 0.0


def sample_if_large(df: pd.DataFrame, max_rows: int, seed: int = 42) -> tuple[pd.DataFrame, bool]:
    if len(df) <= max_rows:
        return df, False
    return df.sample(n=max_rows, random_state=seed), True


def top_n_issues(issues: list[dict], n: int = 500) -> list[dict]:
    issues.sort(key=lambda x: float(x.get("estimated_impact", x.get("score", 0)) or 0), reverse=True)
    return issues[:n]


def concat_chunks(chunks: list[pd.DataFrame]) -> pd.DataFrame:
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def iter_chunks(df: pd.DataFrame, size: int) -> Iterator[pd.DataFrame]:
    if df.empty:
        return
    for start in range(0, len(df), size):
        yield df.iloc[start : start + size]
