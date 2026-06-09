from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.utils.session_auth import get_session_from_request
from app.utils.workspace_modes import workspace_context

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

_LANDING_INDEX = Path("static/landing/index.html")


def _page_ctx(request: Request, **extra: object) -> dict:
    settings = get_settings()
    auth = get_session_from_request(request)
    mode = "authenticated_workspace" if auth else settings.workspace_mode
    ctx = workspace_context(mode)
    return {
        "request": request,
        "brand_name": settings.app_name,
        "brand_tagline": settings.product_tagline,
        "founder_name": settings.founder_name,
        "founder_url": settings.founder_url,
        "product_version": settings.product_version,
        "support_email": settings.assistant_alert_email,
        "auth_user_email": auth.email if auth else None,
        "auth_org_id": auth.organization_id if auth else None,
        **ctx,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def marketing_landing():
    """Premium SaaS landing (React build)."""
    if _LANDING_INDEX.is_file():
        return FileResponse(_LANDING_INDEX, media_type="text/html")
    return HTMLResponse(
        "<h1>CommerceFlow</h1><p>Landing not built. Run: cd landing && npm install && npm run build</p>",
        status_code=503,
    )


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Browsers request /favicon.ico by default — serve branded SVG."""
    svg = Path("static/favicon.svg")
    if svg.is_file():
        return FileResponse(svg, media_type="image/svg+xml")
    raise HTTPException(status_code=404)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_session_from_request(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", _page_ctx(request, page="login"))


@router.get("/dashboard", response_class=HTMLResponse)
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


@router.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    return templates.TemplateResponse("guide.html", _page_ctx(request, page="guide"))


@router.get("/admin/insights", response_class=HTMLResponse)
async def usage_insights_page(request: Request, key: str | None = None):
    """Private usage dashboard — open with ?key= matching USAGE_STATS_KEY on the server."""
    return templates.TemplateResponse(
        "insights.html",
        _page_ctx(request, page="insights", insights_key=key or ""),
    )
