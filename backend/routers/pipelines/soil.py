import logging
from typing import Any
import httpx
import math

from config import config
logger = logging.getLogger("pipelines.soil")

AGRO_SOIL_URL = "http://api.agromonitoring.com/agro/1.0/soil"
AGRO_POLYGONS_URL = "http://api.agromonitoring.com/agro/1.0/polygons"



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
    logger.debug("[soil] creating temp polygon for lat=%s lon=%s", lat, lon)
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
            raise RuntimeError("Failed to create temp polygon")
        data = resp.json()
        polyid = data.get("id") or data.get("_id")
        if not polyid:
            raise RuntimeError("Polygon ID missing in response")
        logger.debug("[soil] created polygon id=%s", polyid)
        return str(polyid)


async def _delete_polygon(polyid: str) -> None:
    try:
        logger.debug("[soil] deleting polygon id=%s", polyid)
        async with httpx.AsyncClient(timeout=15) as client:
            await client.delete(f"{AGRO_POLYGONS_URL}/{polyid}", params={"appid": config.AGRO_API_KEY})
    except Exception:
        pass


async def fetch_soil_data(lat: float, lon: float) -> dict[str, Any]:
    import time
    start = time.monotonic()
    logger.info("[soil] fetch start lat=%s lon=%s", lat, lon)
    polyid = await _create_temp_polygon(lat, lon)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            params = {"polyid": polyid, "appid": config.AGRO_API_KEY}
            soil_resp = await client.get(AGRO_SOIL_URL, params=params)
            if soil_resp.status_code != 200:
                logger.error(f"Soil fetch failed: {soil_resp.text}")
                raise RuntimeError("Failed to fetch soil data")
            data = soil_resp.json()
            dur_ms = int((time.monotonic() - start) * 1000)
            logger.info("[soil] fetch done in %d ms; keys=%s", dur_ms, ",".join(sorted(list(data.keys()))))
            return data
    finally:
        await _delete_polygon(polyid)


__all__ = ["fetch_soil_data"]
