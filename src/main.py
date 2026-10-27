"""Application factory, CORS configuration, custom exception handlers, and lifecycle hooks."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.database import engine, Base
from src.api import api_router
from src.core.exceptions import AppBaseException

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    # Ensure database schema is created
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Dispose engine on shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="High-Trust Dating Application with Verified Credentials and Bayesian Reputation",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppBaseException)
async def custom_exception_handler(request: Request, exc: AppBaseException):
    """Translates domain exceptions into structured JSON error payloads."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Mount all API routes
app.include_router(api_router)


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

dist_path = Path(__file__).parent.parent / "dist"
if dist_path.exists() and (dist_path / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

@app.get("/", tags=["Portal"])
async def root_portal():
    """Redirects root to interactive Swagger UI documentation /docs (Track 2 requirement)."""
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/portal", tags=["Portal"])
async def web_portal():
    """Serves the compiled React frontend Web App if available, otherwise redirects to Swagger."""
    if dist_path.exists() and (dist_path / "index.html").exists():
        return FileResponse(dist_path / "index.html")
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/health", tags=["Health"])
async def health_check():
    """Service liveness probe."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
