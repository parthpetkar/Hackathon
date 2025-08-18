import logging
from typing import Any

import httpx

from config import config

logger = logging.getLogger("pipelines.weather")

AGRO_WEATHER_URL = "https://api.agromonitoring.com/agro/1.0/weather"
AGRO_FORECAST_URL = "https://api.agromonitoring.com/agro/1.0/weather/forecast"


async def fetch_weather_data(lat: float, lon: float) -> dict[str, Any]:
    import time
    start = time.monotonic()
    logger.info("[weather] fetch start lat=%s lon=%s", lat, lon)
    async with httpx.AsyncClient(timeout=15) as client:
        params = {"lat": lat, "lon": lon, "appid": config.AGRO_API_KEY}
        weather = await client.get(AGRO_WEATHER_URL, params=params)
        if weather.status_code != 200:
            logger.error("Weather fetch failed: %s", weather.text)
            raise RuntimeError("Failed to fetch weather data")
        forecast = await client.get(AGRO_FORECAST_URL, params=params)
        if forecast.status_code != 200:
            logger.error("Forecast fetch failed: %s", forecast.text)
            raise RuntimeError("Failed to fetch forecast data")
        wj = weather.json()
        fj = forecast.json()
        fcount = len(fj) if isinstance(fj, list) else (len(fj.get("list", [])) if isinstance(fj, dict) else 0)
        dur_ms = int((time.monotonic() - start) * 1000)
        logger.info("[weather] fetch done in %d ms (forecast items=%s)", dur_ms, fcount)
        return {"today_weather": wj, "forecast": fj}


__all__ = ["fetch_weather_data"]
