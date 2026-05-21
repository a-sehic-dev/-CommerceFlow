import logging
import traceback
from typing import Any

logger = logging.getLogger("commerceflow.analysis")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] commerceflow.analysis — %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def log_stage(stage: str, message: str, **kwargs: Any) -> None:
    extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    line = f"[{stage}] {message}" + (f" | {extra}" if extra else "")
    logger.info(line)


def log_performance(stage: str, **metrics: Any) -> None:
    parts = " | ".join(f"{k}={v}" for k, v in metrics.items())
    logger.info("[performance] %s | %s", stage, parts)


def log_dataset_info(
    stage: str,
    products: int,
    sales: int,
    inventory: int,
    imports: list[dict] | None = None,
    db_path: str | None = None,
    **extra: Any,
) -> None:
    log_stage(
        stage,
        "Dataset loaded",
        products=products,
        sales=sales,
        inventory=inventory,
        db=db_path or "unknown",
        **extra,
    )
    if imports:
        for imp in imports[:5]:
            logger.info(
                "  import id=%s file=%s type=%s status=%s rows=%s success=%s",
                imp.get("id"),
                imp.get("filename"),
                imp.get("source_type"),
                imp.get("status"),
                imp.get("row_count"),
                imp.get("success_count"),
            )


def log_exception(stage: str, exc: BaseException) -> None:
    logger.error("[%s] FAILED: %s: %s", stage, type(exc).__name__, exc)
    logger.error("Traceback:\n%s", traceback.format_exc())


def log_module_result(stage: str, status: str, duration_ms: float, **detail: Any) -> None:
    log_stage(stage, status, duration_ms=f"{duration_ms:.1f}ms", **detail)
