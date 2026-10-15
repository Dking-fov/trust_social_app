"""Router aggregator mounting all domain endpoints under the /api/v1 prefix."""

from fastapi import APIRouter

from src.api.v1.auth import router as auth_router
from src.api.v1.recommendations import router as recommendations_router
from src.api.v1.chat import router as chat_router
from src.api.v1.dates import router as dates_router
from src.api.v1.reviews import router as reviews_router
from src.api.v1.points import router as points_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(recommendations_router)
api_router.include_router(chat_router)
api_router.include_router(dates_router)
api_router.include_router(reviews_router)
api_router.include_router(points_router)

__all__ = ["api_router"]
