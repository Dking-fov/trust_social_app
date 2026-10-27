"""Root API router package aggregating versioned REST and WebSocket endpoints."""

from fastapi import APIRouter

from soulred.api.v1 import v1_router
from soulred.api.ws_chat import router as ws_router

api_router = APIRouter()

# Mount REST v1 routes under /v1 and direct
api_router.include_router(v1_router)

# Mount WebSocket routes
api_router.include_router(ws_router)

__all__ = ["api_router"]
