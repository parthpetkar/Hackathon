import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
import httpx

from .common import run_pipeline
from config import config

router = APIRouter()
logger = logging.getLogger("pipelines.weather")

AGRO_WEATHER_URL = "https://api.agromonitoring.com/agro/1.0/weather"
AGRO_FORECAST_URL = "https://api.agromonitoring.com/agro/1.0/weather/forecast"


class WeatherQuery(BaseModel):
    query: str = Field(...) 
    lat: float = Field(...)
    lon: float = Field(...)


async def fetch_weather_data(lat: float, lon: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        params = {"lat": lat, "lon": lon, "appid": config.AGRO_API_KEY}
        weather = await client.get(AGRO_WEATHER_URL, params=params)
        if weather.status_code != 200:
            logger.error(f"Weather fetch failed: {weather.text}")
            raise HTTPException(status_code=502, detail="Failed to fetch weather data")
        forecast = await client.get(AGRO_FORECAST_URL, params=params)
        if forecast.status_code != 200:
            logger.error(f"Forecast fetch failed: {forecast.text}")
            raise HTTPException(status_code=502, detail="Failed to fetch forecast data")
        return {"today_weather": weather.json(), "forecast": forecast.json()}


@router.post("/pipeline/weather")
async def pipeline_weather(payload: WeatherQuery):
    try:
        result = await run_pipeline(
            payload.query,
            prompt_key="irrigation",
            external_fetcher=fetch_weather_data,
            fetcher_args={"lat": payload.lat, "lon": payload.lon},
        )
        result["pipeline"] = "weather_advice"
        return result
    except Exception as e:
        logger.exception("Weather pipeline failed")
        raise HTTPException(status_code=500, detail=f"Weather pipeline failed: {str(e)}")
