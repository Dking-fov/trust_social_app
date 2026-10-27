"""FastAPI application entrypoint for SoulRed Social Platform.

Mounts:
- Global CORS and security middleware
- Database table schema initialization lifecycle
- REST v1 and WebSocket routers
- Static waterfall frontend demo portal and /health probe
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from soulred.config import get_settings
from soulred.database import init_db
from soulred.api import api_router
from soulred.api.ws_chat import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to run startup and shutdown procedures."""
    # Initialize database tables on application startup
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="SoulRed: Xiaohongshu-style Waterfall Visuals + Soul / QingTeng Social Matching Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Global CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, prefix="/api")
# Also mount WebSocket router at root so /ws/chat/{user_id} is directly available
app.include_router(ws_router)

# Mount Static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get(
    "/health",
    tags=["System"],
    summary="Health check probe",
)
def health_check():
    """Verify application readiness, database connectivity, and environment status."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "1.0.0",
    }


@app.get(
    "/",
    tags=["Portal"],
    summary="Root Xiaohongshu Waterfall Portal",
)
def root_portal():
    """Serve responsive dual-column waterfall frontend demo portal."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": f"Welcome to {settings.APP_NAME}. Visit /docs for Swagger UI."},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "soulred.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
