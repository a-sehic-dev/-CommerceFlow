import pandas as pd
from difflib import SequenceMatcher

from app.config import get_settings
from app.utils.dataframe_ops import top_n_issues
from app.utils.normalization import normalize_sku, normalize_title
from app.utils.scoring import clamp


class DataCleaningEngine:
    """Duplicate detection, field validation, and data quality scoring."""

    FUZZY_THRESHOLD = 88

    def analyze(self, products_df: pd.DataFrame) -> dict:
        if products_df.empty:
            return {"issues": [], "quality_score": 100, "duplicates": [], "missing_fields": []}

        df = products_df.copy()
        issues: list[dict] = []
        duplicates = self._find_duplicate_skus(df)
        issues.extend(duplicates)
        fuzzy_dupes = self._find_fuzzy_title_duplicates(df)
        issues.extend(fuzzy_dupes)
        missing = self._missing_fields(df)
        issues.extend(missing)
        invalid = self._invalid_values(df)
        issues.extend(invalid)
        category_issues = self._category_inconsistencies(df)
        issues.extend(category_issues)

        quality = self._overall_quality_score(df, issues)
        cap = get_settings().analytics_issue_cap
        issues = top_n_issues(issues, cap)

        return {
            "issues": issues,
            "quality_score": quality,
            "duplicates": [i for i in issues if i["type"] == "duplicate_sku"],
            "missing_fields": [i for i in issues if i["type"] == "missing_field"],
            "issue_count": len(issues),
        }

    def _find_duplicate_skus(self, df: pd.DataFrame) -> list[dict]:
        issues = []
        df = df.copy()
        df["_norm_sku"] = df["sku"].apply(normalize_sku)
        dupes = df[df["_norm_sku"].duplicated(keep=False) & (df["_norm_sku"] != "")]
        for sku, group in dupes.groupby("_norm_sku"):
            issues.append({
                "type": "duplicate_sku",
                "sku": sku,
                "count": len(group),
                "score": 80,
                "message": f"Duplicate SKU '{sku}' found {len(group)} times",
                "recommendation": "Merge or deduplicate product records",
            })
        return issues

    def _find_fuzzy_title_duplicates(self, df: pd.DataFrame) -> list[dict]:
        if len(df) > get_settings().fuzzy_duplicate_max_rows:
            return [{
                "type": "fuzzy_duplicate_title",
                "sku": None,
                "score": 50,
                "message": f"Fuzzy title scan skipped ({len(df):,} rows exceeds safe limit)",
                "recommendation": "Run deduplication on a SKU sample or export subset",
            }]
        issues = []
        df = df.copy()
        df["_norm_title"] = df["title"].apply(normalize_title)
        titles = df["_norm_title"].unique().tolist()
        seen: set[tuple[str, str]] = set()

        for i, t1 in enumerate(titles):
            if not t1:
                continue
            for t2 in titles[i + 1 :]:
                if self._title_similarity(t1, t2) >= self.FUZZY_THRESHOLD:
                    pair = tuple(sorted([t1, t2]))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    issues.append({
                        "type": "fuzzy_duplicate_title",
                        "sku": None,
                        "score": 65,
                        "message": f"Similar titles detected: '{t1[:40]}' ~ '{t2[:40]}'",
                        "recommendation": "Review for duplicate listings",
                    })
        return issues[:50]

    def _missing_fields(self, df: pd.DataFrame) -> list[dict]:
        issues = []
        required = ["sku", "title", "price"]
        for field in required:
            if field not in df.columns:
                issues.append({
                    "type": "missing_field",
                    "field": field,
                    "score": 90,
                    "message": f"Required column '{field}' missing from dataset",
                    "recommendation": f"Add {field} column to import file",
                })
                continue
            missing = df[df[field].isna() | (df[field].astype(str).str.strip() == "")]
            if len(missing) > 0:
                issues.append({
                    "type": "missing_field",
                    "field": field,
                    "count": len(missing),
                    "score": 70,
                    "message": f"{len(missing)} rows missing '{field}'",
                    "recommendation": "Fill missing values before analysis",
                })
        return issues

    def _invalid_values(self, df: pd.DataFrame) -> list[dict]:
        issues = []
        if "price" in df.columns:
            invalid_price = df[pd.to_numeric(df["price"], errors="coerce").isna() | (df["price"] < 0)]
            if len(invalid_price) > 0:
                issues.append({
                    "type": "invalid_price",
                    "count": len(invalid_price),
                    "score": 75,
                    "message": f"{len(invalid_price)} rows with invalid pricing",
                    "recommendation": "Correct price formatting",
                })
        return issues

    def _category_inconsistencies(self, df: pd.DataFrame) -> list[dict]:
        issues = []
        if "category" not in df.columns:
            return issues
        cats = df["category"].dropna().astype(str)
        normalized = cats.str.lower().str.strip()
        variants: dict[str, set] = {}
        for orig, norm in zip(cats, normalized):
            variants.setdefault(norm, set()).add(orig)
        for norm, forms in variants.items():
            if len(forms) > 1:
                issues.append({
                    "type": "inconsistent_category",
                    "score": 50,
                    "message": f"Category '{norm}' has {len(forms)} naming variants",
                    "recommendation": "Standardize category naming",
                })
        return issues

    def _overall_quality_score(self, df: pd.DataFrame, issues: list[dict]) -> float:
        penalty = min(len(issues) * 3, 60)
        row_penalty = 0
        if len(df) > 0:
            required = ["sku", "title", "price"]
            for field in required:
                if field in df.columns:
                    missing_pct = df[field].isna().sum() / len(df) * 100
                    row_penalty += missing_pct
        return round(clamp(100 - penalty - row_penalty * 0.2), 1)

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "sku" in out.columns:
            out["sku"] = out["sku"].apply(normalize_sku)
        if "title" in out.columns:
            out["normalized_title"] = out["title"].apply(normalize_title)
        return out
