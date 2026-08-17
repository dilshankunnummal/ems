from contextlib import asynccontextmanager
 
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from app.core.common.redis_client import close_redis_pool
from app.core.config import get_settings
from app.core.database import check_database_connection, dispose_engine
from app.shared.logging import configure_logging
from app.shared.middleware import (
    RequestLoggingMiddleware,
    close_rate_limiter,
    init_rate_limiter,
    register_exception_handlers,
)
 
configure_logging()
logger = structlog.get_logger(__name__)
settings = get_settings()
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", environment=settings.APP_ENV, version=settings.APP_VERSION)
 
    db_ok = await check_database_connection()
    if db_ok:
        logger.info("database_connection_verified")
    else:
        logger.error("database_connection_failed_at_startup")
 
    await init_rate_limiter()
 
    yield
 
    await close_rate_limiter()
    await dispose_engine()
    await close_redis_pool()
    logger.info("app_shutdown")
 
def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Enterprise-grade Employee Management System API — authentication, "
            "employee lifecycle, departments, attendance, leave, documents, "
            "notifications, dashboards, audit trails, and reporting."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
 
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
 
    application.add_middleware(RequestLoggingMiddleware)
 
    register_exception_handlers(application)
 
    @application.get("/", tags=["Health"])
    async def root():
        ...
 
    @application.get("/health", tags=["Health"])
    async def health_check():
        ...
 
    # Register feature routers
    from app.features.auth.api.auth_router import router as auth_router
    from app.features.auth.api.role_router import router as role_router
    from app.features.employee.api.employee_router import router as employee_router
 
    application.include_router(
        auth_router,
        prefix=settings.API_V1_PREFIX,
    )
    application.include_router(
        role_router,
        prefix=settings.API_V1_PREFIX,
    )
    application.include_router(
        employee_router,
        prefix=settings.API_V1_PREFIX,
    )
 
    return application
 
 
app=create_app()
 