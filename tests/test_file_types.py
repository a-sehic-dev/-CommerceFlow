from app.utils.file_types import is_supported_upload, resolve_upload_suffix


def test_double_xlsx_extension():
    assert resolve_upload_suffix("enterprise_sales_q1.xlsx.xlsx") == ".xlsx"
    assert is_supported_upload("warehouse_stock_report.xlsx.xlsx")


def test_standard_extensions():
    assert resolve_upload_suffix("data.csv") == ".csv"
    assert resolve_upload_suffix("catalog.XLSX") == ".xlsx"
