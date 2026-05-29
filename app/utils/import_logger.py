"""Structured logging for dataset imports."""

from __future__ import annotations

import logging
import traceback
from typing import Any

logger = logging.getLogger("commerceflow.import")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] commerceflow.import — %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_import_start(import_id: int, filename: str, source_type: str, dataset_type: str) -> None:
    logger.info(
        "import_start id=%s file=%s source=%s dataset_type=%s",
        import_id,
        filename,
        source_type,
        dataset_type,
    )


def log_import_status(import_id: int, status: str, message: str = "") -> None:
    logger.info("import_status id=%s status=%s %s", import_id, status, message)


def log_import_complete(
    import_id: int,
    *,
    duration_ms: float,
    row_count: int,
    products: int,
    sales: int,
    inventory: int,
    dataset_type: str,
) -> None:
    logger.info(
        "import_complete id=%s duration_ms=%.1f rows=%s products=%s sales=%s inventory=%s type=%s",
        import_id,
        duration_ms,
        row_count,
        products,
        sales,
        inventory,
        dataset_type,
    )


def log_import_failed(import_id: int, error: BaseException) -> None:
    logger.error(
        "import_failed id=%s error=%s: %s\n%s",
        import_id,
        type(error).__name__,
        error,
        traceback.format_exc(),
    )


def log_import_stage(import_id: int, stage: str, **kwargs: Any) -> None:
    extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    logger.info("import_stage id=%s stage=%s%s", import_id, stage, f" | {extra}" if extra else "")


def log_dataset_classification(
    import_id: int,
    *,
    primary_type: str,
    confidence: float | None,
    reason: str,
    method: str,
    scores: dict[str, float] | None = None,
    needs_confirmation: bool = False,
) -> None:
    score_txt = ""
    if scores:
        score_txt = " scores=" + ",".join(f"{k}={v:.2f}" for k, v in sorted(scores.items()))
    logger.info(
        "dataset_classification id=%s type=%s confidence=%s method=%s needs_confirm=%s%s | %s",
        import_id,
        primary_type,
        confidence,
        method,
        needs_confirmation,
        score_txt,
        reason,
    )
