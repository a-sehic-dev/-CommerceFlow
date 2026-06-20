import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, alerts, analytics, assistant, auth, exports, feedback, imports, integrations, pages, reports_schedule, team, usage
from app.config import ensure_directories, get_settings
from app.middleware import usage_page_middleware
from app.database import init_db
from app.utils.app_timezone import as_local_iso
from app.utils.json_safe import sanitize_for_json

ENCODERS_BY_TYPE[datetime] = as_local_iso

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    await init_db()
    from app.database import async_session_factory
    from app.services.import_stale_recovery import recover_stale_imports

    async with async_session_factory() as session:
        recovered = await recover_stale_imports(session)
        await session.commit()
        if recovered:
            log_early = logging.getLogger("commerceflow")
            log_early.info("Recovered %s stale import(s) on startup", recovered)
    from app.services.import_registry import release_all_imports

    await release_all_imports()
    from app.utils.cache import analytics_cache

    analytics_cache.invalidate()
    from app.utils.chart_images import charts_available

    log = logging.getLogger("commerceflow")
    if charts_available():
        log.info("Executive workbook charts: matplotlib Agg backend ready")
    else:
        log.warning(
            "Executive workbook charts: matplotlib/Pillow not available — "
            "run .venv\\Scripts\\pip install -r requirements.txt and restart with .venv\\Scripts\\python.exe run.py"
        )

    from app.services.demo_bootstrap import run_startup_demo_bootstrap, should_auto_bootstrap

    bootstrap_task: asyncio.Task | None = None
    if should_auto_bootstrap():
        log.info("Scheduling Atlas demo bootstrap (background)")
        bootstrap_task = asyncio.create_task(run_startup_demo_bootstrap())

    yield

    if bootstrap_task and not bootstrap_task.done():
        bootstrap_task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Ecommerce intelligence and operational automation platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.middleware("http")(usage_page_middleware)

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(assistant.router)
    app.include_router(imports.router)
    app.include_router(integrations.router)
    app.include_router(team.router)
    app.include_router(reports_schedule.router)
    app.include_router(analytics.router)
    app.include_router(alerts.router)
    app.include_router(exports.router)
    app.include_router(feedback.router)
    app.include_router(usage.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logging.getLogger("commerceflow").exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        content = {
            "success": False,
            "message": str(exc),
            "error_type": type(exc).__name__,
        }
        if settings.debug:
            content["traceback"] = traceback.format_exc()
        return JSONResponse(status_code=500, content=sanitize_for_json(content))

    @app.get("/api/health")
    async def health():
        from app.utils.app_timezone import APP_TZ_NAME, now_local
        from app.utils.database_url import is_postgres_url
        from app.utils.founder_email import smtp_configured

        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.product_version,
            "founder": settings.founder_name,
            "timezone": APP_TZ_NAME,
            "server_time": now_local().isoformat(),
            "database_backend": "postgresql" if is_postgres_url(settings.database_url) else "sqlite",
            "smtp_configured": smtp_configured(),
            "shopify_oauth_ready": bool(settings.shopify_api_key and settings.shopify_api_secret),
        }

    return app


app = create_app()
