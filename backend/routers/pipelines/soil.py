import logging
from typing import Any, Optional
import httpx

from config import config

logger = logging.getLogger("pipelines.soil")

DATA_GOV_SOIL_URL = "https://api.data.gov.in/resource/4554a3c8-74e3-4f93-8727-8fd92161e345"


async def fetch_soil_data(
    *,
    state: Optional[str] = None,
    district: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    agency_name: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """Fetch soil moisture records from data.gov.in resource.

    Returns dict: { "soil_records": [...], "total": int }
    """
    import time
    start = time.monotonic()
    logger.info("[soil] (data.gov.in) fetch start state=%s district=%s year=%s month=%s limit=%s offset=%s",
                state, district, year, month, limit, offset)
    params: dict[str, Any] = {
        "api-key": config.DATA_GOV_API_KEY,
        "format": "json",
        "limit": limit,
        "offset": offset,
    }
    def add_filter(k: str, v: Optional[str]):
        if v is not None and str(v).strip():
            params[f"filters[{k}]"] = str(v).strip()

    add_filter("State", state)
    add_filter("District", district)
    add_filter("Year", year)
    add_filter("Month", month)
    add_filter("Agency_name", agency_name)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(DATA_GOV_SOIL_URL, params=params)
        if resp.status_code != 200:
            logger.error("Soil API failed: %s %s", resp.status_code, resp.text)
            raise RuntimeError("Failed to fetch soil data")
        data = resp.json()
        records = data.get("records") or []
        total = int(data.get("total") or len(records))
        dur = int((time.monotonic() - start) * 1000)
        logger.info("[soil] (data.gov.in) done in %d ms; records=%d total=%d", dur, len(records), total)
        print(records)
        return {"soil_records": records, "total": total}


__all__ = ["fetch_soil_data"]
