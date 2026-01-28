from fastapi import APIRouter
from .health import ROUTER as health_router
from .hass import router as hass_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(health_router, tags=["Health"])
v1_router.include_router(hass_router, prefix="/hass", tags=["Home Assistant"])
