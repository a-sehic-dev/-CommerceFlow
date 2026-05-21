from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.services.analytics_orchestrator import AnalyticsOrchestrator


class AlertService:
    MAX_PER_TYPE = 12

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_from_analysis(self) -> list[Alert]:
        orchestrator = AnalyticsOrchestrator(self.session)
        from app.services.active_dataset_service import ActiveDatasetService

        active = await ActiveDatasetService(self.session).get_active()
        if not active.has_selection:
            return []
        selection = {
            "products_import_id": active.products_import_id,
            "sales_import_id": active.sales_import_id,
            "inventory_import_id": active.inventory_import_id,
        }
        pipeline = await orchestrator.run_analysis_pipeline(use_cache=True, selection=selection)
        analysis = pipeline.get("result") or {}
        candidates: list[dict] = []

        for issue in analysis["profit_leakage"].get("issues", []):
            candidates.append(
                {
                    "alert_type": issue.get("type", "profit_leakage"),
                    "severity": issue.get("severity", "medium"),
                    "title": issue.get("type", "Issue").replace("_", " ").title(),
                    "message": issue.get("message", ""),
                    "entity_id": issue.get("sku"),
                    "score": issue.get("score"),
                }
            )

        for inv_alert in analysis["inventory_risk"].get("alerts", []):
            candidates.append(
                {
                    "alert_type": inv_alert.get("type", "inventory"),
                    "severity": inv_alert.get("severity", "medium"),
                    "title": inv_alert.get("type", "inventory").replace("_", " ").title(),
                    "message": inv_alert.get("message", inv_alert.get("recommendation", "")),
                    "entity_id": inv_alert.get("sku"),
                    "score": inv_alert.get("score"),
                }
            )

        for issue in analysis["data_cleaning"].get("issues", []):
            candidates.append(
                {
                    "alert_type": issue.get("type", "data_quality"),
                    "severity": "medium" if issue.get("score", 0) < 80 else "low",
                    "title": issue.get("type", "data_quality").replace("_", " ").title(),
                    "message": issue.get("message", ""),
                    "entity_id": issue.get("sku"),
                    "score": issue.get("score"),
                }
            )

        diversified = self._diversify(candidates)
        alerts: list[Alert] = []
        for item in diversified:
            alert = Alert(**item)
            alerts.append(alert)
            self.session.add(alert)

        await self.session.flush()
        analytics_cache_invalidate()
        return alerts

    def _diversify(self, candidates: list[dict]) -> list[dict]:
        """Spread alerts across issue types; avoid repetitive duplicates."""
        by_type: dict[str, list[dict]] = {}
        for item in candidates:
            by_type.setdefault(item["alert_type"], []).append(item)

        priority_types = [
            "negative_profit",
            "dead_inventory",
            "low_margin",
            "stockout_risk",
            "low_stock",
            "overstock",
            "duplicate_sku",
            "missing_inventory",
            "suspicious_discount",
            "suspicious_pricing",
            "revenue_drop",
            "fuzzy_duplicate_title",
            "missing_field",
        ]

        ordered_types = [t for t in priority_types if t in by_type]
        ordered_types.extend(sorted(t for t in by_type if t not in ordered_types))

        seen: set[tuple] = set()
        result: list[dict] = []
        per_type_count: dict[str, int] = {}

        while len(result) < 80:
            added = False
            for alert_type in ordered_types:
                if per_type_count.get(alert_type, 0) >= self.MAX_PER_TYPE:
                    continue
                bucket = by_type.get(alert_type, [])
                if not bucket:
                    continue
                item = bucket.pop(0)
                key = (alert_type, item.get("entity_id"), (item.get("message") or "")[:80])
                if key in seen:
                    continue
                seen.add(key)
                result.append(item)
                per_type_count[alert_type] = per_type_count.get(alert_type, 0) + 1
                added = True
                if len(result) >= 80:
                    break
            if not added:
                break
        return result

    async def list_alerts(
        self,
        severity: str | None = None,
        alert_type: str | None = None,
        unread_only: bool = False,
        limit: int = 100,
    ) -> list[Alert]:
        q = select(Alert).where(Alert.is_dismissed == False).order_by(Alert.created_at.desc())  # noqa: E712
        if severity:
            q = q.where(Alert.severity == severity)
        if alert_type:
            q = q.where(Alert.alert_type == alert_type)
        if unread_only:
            q = q.where(Alert.is_read == False)  # noqa: E712
        q = q.limit(limit)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def mark_read(self, alert_id: int) -> Alert | None:
        result = await self.session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            alert.is_read = True
            await self.session.flush()
        return alert

    async def dismiss(self, alert_id: int) -> Alert | None:
        result = await self.session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            alert.is_dismissed = True
            await self.session.flush()
        return alert


def analytics_cache_invalidate() -> None:
    from app.utils.cache import analytics_cache

    analytics_cache.invalidate()
