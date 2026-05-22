from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")


def _page_ctx(request: Request, **extra: object) -> dict:
    settings = get_settings()
    return {
        "request": request,
        "brand_name": settings.app_name,
        "brand_tagline": settings.product_tagline,
        "founder_name": settings.founder_name,
        "founder_url": settings.founder_url,
        "product_version": settings.product_version,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", _page_ctx(request, page="overview"))


@router.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    return templates.TemplateResponse("products.html", _page_ctx(request, page="products"))


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    return templates.TemplateResponse("inventory.html", _page_ctx(request, page="inventory"))


@router.get("/profit", response_class=HTMLResponse)
async def profit_page(request: Request):
    return templates.TemplateResponse("profit.html", _page_ctx(request, page="profit"))


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request):
    return templates.TemplateResponse("alerts.html", _page_ctx(request, page="alerts"))


@router.get("/imports", response_class=HTMLResponse)
async def imports_page(request: Request):
    return templates.TemplateResponse("imports.html", _page_ctx(request, page="imports"))


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    return templates.TemplateResponse("reports.html", _page_ctx(request, page="reports"))
