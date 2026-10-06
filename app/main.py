from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("Starting up %s v%s", settings.PROJECT_NAME, settings.VERSION)
    try:
        init_db()
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
    yield
    # Shutdown
    logger.info("Shutting down %s", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise-grade AI Lead Recovery Engine designed to identify inactive or high-intent leads, analyze multi-turn conversations, enforce multi-tenancy, and provide structured recovery recommendations.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please check server logs.",
            "path": request.url.path,
        },
    )


# Root & Health Check Endpoints
@app.get("/", tags=["Health"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "documentation": "/docs",
        "health_check": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    db_type = "postgresql" if settings.DATABASE_URL.startswith("postgresql") else "sqlite"
    return {
        "status": "healthy",
        "provider": settings.LLM_PROVIDER,
        "database": f"{db_type} (connected)",
    }


# Include V1 Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
