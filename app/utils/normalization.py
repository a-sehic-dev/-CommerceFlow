import re
import unicodedata


def normalize_title(title: str) -> str:
    if not title:
        return ""
    text = unicodedata.normalize("NFKD", str(title))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text.lower().strip())
    text = re.sub(r"[^\w\s\-]", "", text)
    return text.strip()


def normalize_sku(sku: str) -> str:
    if not sku:
        return ""
    return re.sub(r"\s+", "", str(sku).upper().strip())


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and value != value):
            return default
        cleaned = str(value).replace("$", "").replace(",", "").strip()
        return float(cleaned) if cleaned else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default
