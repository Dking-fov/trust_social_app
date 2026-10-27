"""V1 REST API Router aggregating all sub-domain endpoints."""

from fastapi import APIRouter

from soulred.api.v1.auth import router as auth_router
from soulred.api.v1.users import router as users_router
from soulred.api.v1.posts import router as posts_router
from soulred.api.v1.feed import router as feed_router
from soulred.api.v1.matching import router as matching_router
from soulred.api.v1.chat import router as chat_router
from soulred.api.v1.circles import router as circles_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(posts_router)
v1_router.include_router(feed_router)
v1_router.include_router(matching_router)
v1_router.include_router(chat_router)
v1_router.include_router(circles_router)

__all__ = ["v1_router"]
