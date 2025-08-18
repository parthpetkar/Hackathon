import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
import httpx
import math

from .common import run_pipeline
from config import config

router = APIRouter()
logger = logging.getLogger("pipelines.uv")

AGROMONITORING_UV_URL = "http://api.agromonitoring.com/agro/1.0/uvi"
AGRO_POLYGONS_URL = "http://api.agromonitoring.com/agro/1.0/polygons"


class UvQuery(BaseModel):
    query: str = Field(...)
    lat: float = Field(...)
    lon: float = Field(...)

def _square_polygon(lat: float, lon: float, radius_km: float = 5.0) -> list[list[float]]:
    half_km = radius_km / 2.0
    dlat = half_km / 111.32
    lat_rad = math.radians(lat)
    km_per_deg_lon = 111.32 * max(0.0001, math.cos(lat_rad))
    dlon = half_km / km_per_deg_lon
    return [
        [lon - dlon, lat - dlat],
        [lon - dlon, lat + dlat],
        [lon + dlon, lat + dlat],
        [lon + dlon, lat - dlat],
        [lon - dlon, lat - dlat],
    ]

async def _create_temp_polygon(lat: float, lon: float) -> str:
    coords = _square_polygon(lat, lon, radius_km=5.0)
    payload = {
        "name": f"temp-{lat:.5f},{lon:.5f}",
        "geo_json": {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(AGRO_POLYGONS_URL, params={"appid": config.AGRO_API_KEY}, json=payload)
        if resp.status_code not in (200, 201):
            logger.error(f"Create polygon failed: {resp.text}")
            raise HTTPException(status_code=502, detail="Failed to create temp polygon")
        data = resp.json()
        polyid = data.get("id") or data.get("_id")
        if not polyid:
            raise HTTPException(status_code=502, detail="Polygon ID missing in response")
        return str(polyid)
    
async def _delete_polygon(polyid: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.delete(f"{AGRO_POLYGONS_URL}/{polyid}", params={"appid": config.AGRO_API_KEY})
    except Exception:
        pass

async def fetch_uv_data(lat: float, lon: float) -> dict[str, Any]:
    polyid = await _create_temp_polygon(lat, lon)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            params = {"polyid": polyid, "appid": config.AGRO_API_KEY}
            soil_resp = await client.get(AGROMONITORING_UV_URL, params=params)
            if soil_resp.status_code != 200:
                logger.error(f"Soil fetch failed: {soil_resp.text}")
                raise HTTPException(status_code=502, detail="Failed to fetch soil data")
            return soil_resp.json()
    finally:
        await _delete_polygon(polyid)


@router.post("/pipeline/uv")
async def pipeline_uv(payload: UvQuery):
    try:
        result = await run_pipeline(
            payload.query,
            prompt_key="general",
            external_fetcher=fetch_uv_data,
            fetcher_args={"lat": payload.lat, "lon": payload.lon},
        )
        result["pipeline"] = "uv_advice"
        return result
    except Exception as e:
        logger.exception("UV pipeline failed")
        raise HTTPException(status_code=500, detail=f"UV pipeline failed: {str(e)}")
