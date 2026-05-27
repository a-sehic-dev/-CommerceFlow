"""Render executive charts as PNG bytes for reliable Excel embedding."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Callable

logger = logging.getLogger("commerceflow.charts")

CHART_NAVY = "#1E3A8A"
CHART_INDIGO = "#4F46E5"
CHART_SKY = "#0EA5E9"
CHART_GREEN = "#059669"
CHART_AMBER = "#D97706"
CHART_RED = "#DC2626"
DOUGHNUT_COLORS = [CHART_NAVY, CHART_INDIGO, CHART_SKY, CHART_GREEN, CHART_AMBER, CHART_RED, "#7C3AED", "#64748B"]
RISK_COLORS = {"Low": CHART_GREEN, "Medium": CHART_AMBER, "Critical": CHART_RED}

_plt_module: Any | None = None


def charts_available() -> bool:
    """True when matplotlib Agg + Pillow can render chart PNGs for openpyxl embedding."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: F401
        from PIL import Image  # noqa: F401

        return True
    except ImportError:
        return False
    except Exception as exc:
        logger.warning("matplotlib/Pillow unavailable: %s", exc)
        return False


def _get_plt():
    global _plt_module
    try:
        import matplotlib

        matplotlib.use("Agg")
        if _plt_module is None:
            import matplotlib.pyplot as plt

            _plt_module = plt
        return _plt_module
    except ImportError:
        return None
    except Exception as exc:
        logger.warning("matplotlib backend error: %s", exc)
        return None


def _fig_bytes(fig, dpi: int = 120) -> bytes:
    plt = _get_plt()
    if plt is None:
        return b""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _safe_render(render_fn: Callable[[], bytes]) -> bytes:
    try:
        return render_fn()
    except Exception as exc:
        logger.warning("Chart render skipped: %s", exc)
        return b""


def render_revenue_line_png(labels: list[str], values: list[float]) -> bytes:
    def _render() -> bytes:
        plt = _get_plt()
        if plt is None:
            return b""
        fig, ax = plt.subplots(figsize=(5.2, 3.2))
        x = range(len(values))
        ax.plot(x, values, color=CHART_NAVY, linewidth=2.2, marker="o", markersize=3.5)
        ax.set_title("Revenue Trend (Daily)", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
        ax.set_ylabel("Revenue ($)", fontsize=9, color="#475569")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if labels:
            step = max(1, len(labels) // 6)
            ticks = list(range(0, len(labels), step))
            ax.set_xticks(ticks)
            ax.set_xticklabels([labels[i][:10] for i in ticks], rotation=35, ha="right", fontsize=7)
        fig.tight_layout()
        return _fig_bytes(fig)

    return _safe_render(_render)


def render_category_doughnut_png(labels: list[str], values: list[float]) -> bytes:
    def _render() -> bytes:
        plt = _get_plt()
        if plt is None:
            return b""
        fig, ax = plt.subplots(figsize=(4.8, 3.2))
        colors = DOUGHNUT_COLORS[: len(values)]
        wedges, _, autotexts = ax.pie(
            values,
            labels=None,
            autopct="%1.0f%%",
            startangle=90,
            colors=colors,
            pctdistance=0.78,
            wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 1.2},
        )
        for t in autotexts:
            t.set_fontsize(8)
            t.set_color("white")
            t.set_fontweight("bold")
        ax.set_title("Category Revenue Mix", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
        ax.legend(
            wedges,
            [f"{lb} (${v:,.0f})" for lb, v in zip(labels, values, strict=True)],
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=7,
            frameon=False,
        )
        fig.tight_layout()
        return _fig_bytes(fig)

    return _safe_render(_render)


def render_inventory_bar_png(labels: list[str], values: list[float]) -> bytes:
    def _render() -> bytes:
        plt = _get_plt()
        if plt is None:
            return b""
        fig, ax = plt.subplots(figsize=(4.6, 3.2))
        colors = [RISK_COLORS.get(lb, CHART_NAVY) for lb in labels]
        bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=1)
        ax.set_title("Inventory Risk Breakdown", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
        ax.set_ylabel("SKU Count", fontsize=9, color="#475569")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for bar, val in zip(bars, values, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{int(val)}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        fig.tight_layout()
        return _fig_bytes(fig)

    return _safe_render(_render)
