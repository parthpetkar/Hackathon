import logging
from typing import Any

import httpx

from config import config

logger = logging.getLogger("pipelines.weather")

# OpenWeather endpoints
OWM_BASE = "https://api.openweathermap.org"
OWM_CURRENT_URL = f"{OWM_BASE}/data/2.5/weather"
OWM_DAILY16_URL = f"{OWM_BASE}/data/2.5/forecast/daily"  # 16-day daily forecast
OWM_CLIMATE30_URL = f"{OWM_BASE}/data/2.5/forecast/climate"  # 30-day climate forecast


async def fetch_weather_data(lat: float, lon: float) -> dict[str, Any]:
    """Fetch current weather, 16-day daily forecast, and 30-day climate forecast from OpenWeather.

    Returns a dict with keys:
    - today_weather: dict
    - forecast: list|dict (16-day daily)
    - climate_30d: list|dict (optional, if plan allows)
    """
    import time
    start = time.monotonic()
    logger.info("[weather] (OWM) fetch start lat=%s lon=%s", lat, lon)

    if not config.OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=20) as client:
        # Always request metric units for human-friendly outputs
        base_params = {"lat": lat, "lon": lon, "appid": config.OPENWEATHER_API_KEY, "units": "metric"}

        # Current weather
        w_resp = await client.get(OWM_CURRENT_URL, params=base_params)
        if w_resp.status_code != 200:
            logger.error("OWM current weather failed: %s", w_resp.text)
            raise RuntimeError("Failed to fetch current weather")
        today = w_resp.json()

        # 16-day daily forecast (cnt=16)
        f_params = dict(base_params)
        f_params["cnt"] = 16
        f_resp = await client.get(OWM_DAILY16_URL, params=f_params)
        if f_resp.status_code not in (200, 204):
            logger.warning("OWM 16-day daily forecast failed: %s", f_resp.text)
            forecast = []
        else:
            f_json = f_resp.json()
            # Some responses wrap data in { city, cnt, list: [...] }
            forecast = f_json.get("list", f_json if isinstance(f_json, list) else [])

        # 30-day climate forecast (cnt=30) — may require paid plan; tolerate failure
        c_params = dict(base_params)
        c_params["cnt"] = 30
        c_resp = await client.get(OWM_CLIMATE30_URL, params=c_params)
        climate_30d = None
        if c_resp.status_code in (200, 204):
            c_json = c_resp.json()
            climate_30d = c_json.get("list", c_json if isinstance(c_json, list) else c_json)
        else:
            logger.info("OWM 30d climate unavailable: %s", c_resp.text)

        dur_ms = int((time.monotonic() - start) * 1000)
        fcount = len(forecast) if isinstance(forecast, list) else (len(forecast.get("list", [])) if isinstance(forecast, dict) else 0)
        logger.info("[weather] (OWM) fetch done in %d ms (daily16 items=%s, climate=%s)", dur_ms, fcount, "ok" if climate_30d is not None else "na")
        return {"today_weather": today, "forecast": forecast, "climate_30d": climate_30d}


__all__ = ["fetch_weather_data"]
