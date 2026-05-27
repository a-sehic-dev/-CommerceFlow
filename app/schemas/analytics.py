from typing import Any

from pydantic import BaseModel, Field

from app.schemas.datetime_types import LocalDateTime


class DashboardMetrics(BaseModel):
    total_revenue: float | None = None
    total_orders: int | None = None
    avg_order_value: float | None = None
    gross_margin_pct: float | None = None
    inventory_efficiency: float | None = None
    operational_risk_score: float | None = None
    active_alerts: int | None = None
    product_count: int | None = None
    dead_inventory_value: float | None = None
    profit_leakage_estimate: float | None = None


class ProductInsight(BaseModel):
    sku: str
    title: str
    category: str | None = None
    revenue: float = 0
    units_sold: int = 0
    margin_pct: float | None = None
    health_score: float = 0
    trend: str = "stable"
    rank: int = 0


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: str
    score: float | None = None
    is_read: bool = False
    created_at: LocalDateTime


class ImportStatusResponse(BaseModel):
    id: int
    filename: str
    display_name: str = ""
    company_name: str | None = None
    source_label: str = "Uploaded"
    source_type: str
    dataset_type: str = "unknown"
    detection_confidence: float | None = None
    detection_reason: str | None = None
    needs_type_confirmation: bool = False
    products_imported: int = 0
    sales_imported: int = 0
    inventory_imported: int = 0
    status: str
    row_count: int
    success_count: int
    error_count: int
    started_at: LocalDateTime
    completed_at: LocalDateTime | None = None


class ConfirmDatasetTypeRequest(BaseModel):
    dataset_type: str = Field(pattern="^(products|sales|inventory)$")


class BulkDeleteImportsRequest(BaseModel):
    import_ids: list[int] = Field(default_factory=list, min_length=1)


class ExportRequest(BaseModel):
    format: str = Field(default="csv", pattern="^(csv|xlsx|json)$")
    report_type: str = Field(default="summary")


class ExportJobRequest(BaseModel):
    report_type: str = Field(default="enterprise")
    format: str = Field(default="xlsx", pattern="^(csv|xlsx|json)$")


class AnalyticsPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
