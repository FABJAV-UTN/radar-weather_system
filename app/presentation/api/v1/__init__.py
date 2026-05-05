"""API v1 routers."""

from app.presentation.api.v1.radar import router as radar_router
from app.presentation.api.v1.images import router as images_router

__all__ = ["radar_router", "images_router"]
