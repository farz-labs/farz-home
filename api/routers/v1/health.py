"""This module initializes the Health ROUTER."""

from fastapi import APIRouter

ROUTER = APIRouter()


@ROUTER.get("/health")
async def health_check() -> dict[str, str]:
    """Checks health of the server"""

    return {
        "status": "ok",
    }
