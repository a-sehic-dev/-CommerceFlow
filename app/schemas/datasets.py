from pydantic import BaseModel, Field

from app.schemas.datetime_types import LocalDateTime


class ImportCatalogItem(BaseModel):
    id: int
    filename: str
    display_name: str = ""
    company_name: str | None = None
    source_label: str = "Uploaded"
    engine_title: str = ""
    status_label: str = ""
    dataset_type: str
    status: str
    row_count: int
    success_count: int
    products_imported: int = 0
    sales_imported: int = 0
    inventory_imported: int = 0
    started_at: LocalDateTime
    label: str = ""
    subtitle: str = ""
    eligible_for: list[str] = Field(default_factory=list)
    detection_confidence: float | None = None
    needs_type_confirmation: bool = False


class ImportCatalogResponse(BaseModel):
    products: list[ImportCatalogItem] = Field(default_factory=list)
    sales: list[ImportCatalogItem] = Field(default_factory=list)
    inventory: list[ImportCatalogItem] = Field(default_factory=list)
    all: list[ImportCatalogItem] = Field(default_factory=list)


class ActiveDatasetsResponse(BaseModel):
    products_import_id: int | None = None
    sales_import_id: int | None = None
    inventory_import_id: int | None = None
    products: ImportCatalogItem | None = None
    sales: ImportCatalogItem | None = None
    inventory: ImportCatalogItem | None = None
    has_selection: bool = False
    has_generated_analysis: bool = False
    analysis_generated_at: LocalDateTime | None = None


class AnalysisRunRequest(BaseModel):
    products_import_id: int | None = None
    sales_import_id: int | None = None
    inventory_import_id: int | None = None
    rebuild_dashboard: bool = True
    regenerate_alerts: bool = True
    recalculate_inventory_risks: bool = True
    export_report_after: bool = False
