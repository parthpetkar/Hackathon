from fastapi import APIRouter

# Aggregate sub-routers under a single router for easy inclusion in app.py
router = APIRouter()

try:
    from .general import router as general_router
    router.include_router(general_router)
except Exception:
    pass

try:
    from .weather import router as weather_router
    router.include_router(weather_router)
except Exception:
    pass

try:
    from .soil import router as soil_router
    router.include_router(soil_router)
except Exception:
    pass

try:
    from .uv import router as uv_router
    router.include_router(uv_router)
except Exception:
    pass
from fastapi import APIRouter

from .common import run_pipeline  # re-export for api dispatch
from .weather import router as weather_router
from .soil import router as soil_router
from .uv import router as uv_router

router = APIRouter()
router.include_router(weather_router)
router.include_router(soil_router)
router.include_router(uv_router)

__all__ = ["router", "run_pipeline"]
