"""Pipelines package: fetch-only helpers for external data.

No FastAPI routers are exposed. The orchestrator in routers/api.py plans
fetchers via the pipeline selector and runs them through run_multi_pipeline.
"""

from .weather import fetch_weather_data
from .soil import fetch_soil_data
from .uv import fetch_uv_data
from .mandi import fetch_mandi_data, fetch_mandi_data_from_query

__all__ = [
	"fetch_weather_data",
	"fetch_soil_data",
	"fetch_uv_data",
	"fetch_mandi_data",
	"fetch_mandi_data_from_query",
]
