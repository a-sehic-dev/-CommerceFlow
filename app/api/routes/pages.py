from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.services.plan_service import PlanService
from app.services.team_service import TeamService
from app.utils.plan_limits import plan_rank
from app.utils.session_auth import get_session_from_request
from app.utils.workspace_modes import workspace_context

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

_LANDING_INDEX = Path("static/landing/index.html")


async def _page_ctx(request: Request, db: AsyncSession, **extra: object) -> dict:
    settings = get_settings()
    auth = get_session_from_request(request)
    mode = "authenticated_workspace" if auth else settings.workspace_mode
    ctx = workspace_context(mode)

    billing_plan = None
    billing_summary = ""
    billing_detail = ""
    billing_show_pro = False
    billing_show_team = False
    billing_show_ultra = False
    auth_user_role = None

    if auth:
        user = await db.scalar(select(User).where(User.id == auth.user_id))
        auth_user_role = user.role if user else "owner"
        org = await db.scalar(select(Organization).where(Organization.id == auth.organization_id))
        plan_slug = org.plan if org else "starter"
        plan_svc = PlanService(db)
        limits = await plan_svc.limits_payload(auth.organization_id)
        seats_used = await TeamService(db).seat_count(auth.organization_id)
        rank = plan_rank(plan_slug)
        is_owner = (auth_user_role or "owner").lower() == "owner"

        billing_plan = limits
        billing_summary = limits.get("summary") or ""
        billing_detail = f"{limits.get('price_hint', '')} · {seats_used}/{limits.get('max_seats', 1)} seats"
        if is_owner:
            billing_show_pro = rank < 1
            billing_show_team = rank < 2
            billing_show_ultra = rank < 3

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
        "auth_user_role": auth_user_role,
        "billing_plan": billing_plan,
        "billing_summary": billing_summary,
        "billing_detail": billing_detail,
        "billing_show_pro": billing_show_pro,
        "billing_show_team": billing_show_team,
        "billing_show_ultra": billing_show_ultra,
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
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    if get_session_from_request(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", await _page_ctx(request, db, page="login"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("dashboard.html", await _page_ctx(request, db, page="overview"))


@router.get("/products", response_class=HTMLResponse)
async def products_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("products.html", await _page_ctx(request, db, page="products"))


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("inventory.html", await _page_ctx(request, db, page="inventory"))


@router.get("/profit", response_class=HTMLResponse)
async def profit_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("profit.html", await _page_ctx(request, db, page="profit"))


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("alerts.html", await _page_ctx(request, db, page="alerts"))


@router.get("/imports", response_class=HTMLResponse)
async def imports_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("imports.html", await _page_ctx(request, db, page="imports"))


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("reports.html", await _page_ctx(request, db, page="reports"))


@router.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("guide.html", await _page_ctx(request, db, page="guide"))


@router.get("/admin/insights", response_class=HTMLResponse)
async def usage_insights_page(request: Request, key: str | None = None, db: AsyncSession = Depends(get_db)):
    """Private usage dashboard — open with ?key= matching USAGE_STATS_KEY on the server."""
    return templates.TemplateResponse(
        "insights.html",
        await _page_ctx(request, db, page="insights", insights_key=key or ""),
    )
