import json
import os
import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config import config
import json
import os
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from langchain.prompts import PromptTemplate
from api.common import run_chain
from routers.pipelines.weather import fetch_weather_data
from routers.pipelines.soil import fetch_soil_data
from routers.pipelines.mandi import fetch_mandi_data_from_query
import httpx

logger = logging.getLogger("pipeline_selector")


@dataclass(frozen=True)
class PipelineDef:
    id: str
    description: str
    prompt_key: str


# Location of the pipelines JSON file
PIPELINES_FILE = os.getenv(
    "PIPELINES_FILE",
    os.path.join(os.path.dirname(__file__), "pipelines.json"),
)

_PIPELINES_CACHE: Optional[List[PipelineDef]] = None


def load_pipelines() -> List[PipelineDef]:
    global _PIPELINES_CACHE
    if _PIPELINES_CACHE is not None:
        logger.debug("Pipelines loaded from cache: %d", len(_PIPELINES_CACHE))
        return _PIPELINES_CACHE

    with open(PIPELINES_FILE, "r", encoding="utf-8") as f:
        data: List[dict] = json.load(f)

    _PIPELINES_CACHE = [
        PipelineDef(
            id=str(d.get("id")),
            description=str(d.get("description", "")),
            prompt_key=str(d.get("prompt_key")),
        )
        for d in data
        if d.get("id") and d.get("prompt_key")
    ]
    logger.info("Loaded %d pipelines from %s", len(_PIPELINES_CACHE), PIPELINES_FILE)
    return _PIPELINES_CACHE


def ensure_pipeline_index() -> None:
    """No-op for LLM routing; kept for startup compatibility."""
    try:
        _ = load_pipelines()
        logger.debug("Pipeline index ensured (no-op)")
    except Exception as e:
        logger.error("Failed to ensure pipeline index: %s", e)


# Removed single-pipeline routing; only multi-routing is supported.


def _multi_routing_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["pipelines", "question"],
        template=(
            "You are an expert router that maps a user query to one or more pipelines.\n"
            "Given pipelines (id, description, prompt_key), choose ALL that are relevant.\n"
            "Return ONLY JSON of the form: {{\n  \"pipeline_ids\": [\"id1\", \"id2\"],\n  \"reason\": \"short rationale\"\n}}\n\n"
            "Pipelines:\n{pipelines}\n\n"
            "Query:\n{question}"
        ),
    )


def select_pipelines(query: str) -> List[PipelineDef]:
    pipelines = load_pipelines()
    if not pipelines:
        return []
    if not query:
        return [pipelines[-1]]
    logger.info("Routing multi-pipeline for query: %s", query)
    plist = [
        {"id": p.id, "description": p.description, "prompt_key": p.prompt_key}
        for p in pipelines
    ]
    prompt = _multi_routing_prompt()
    llm_out = run_chain(prompt, {"pipelines": json.dumps(plist, ensure_ascii=False), "question": query})
    logger.debug("Multi-route LLM output: %s", llm_out)
    try:
        obj = json.loads(llm_out)
        ids = obj.get("pipeline_ids") or []
        if isinstance(ids, list):
            id_to_def = {p.id: p for p in pipelines}
            picked = [id_to_def[i] for i in ids if i in id_to_def]
            if picked:
                logger.info("Selected pipelines: %s", ", ".join([p.id for p in picked]))
                return picked
    except Exception:
        logger.warning("Failed to parse multi-route output; using default pipeline")
    # Fallback to default (first) pipeline without single-route LLM
    logger.info("Fallback selected pipeline: %s", pipelines[0].id)
    return [pipelines[0]]


# Single-pipeline routing removed.


def _latlon_extraction_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["q"],
        template=(
            "Extract latitude and longitude from the query if present. Return ONLY JSON:"
            " {\n  \"lat\": <float or null>,\n  \"lon\": <float or null>\n}\n\nQuery: {q}"
        ),
    )

def _region_extraction_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["q"],
        template=(
            "If the query mentions a location/region (village, city, district, state, market), "
            "return ONLY JSON with a single key 'region' as a string; otherwise region=null.\n"
            "{\n  \"region\": <string or null>\n}\n\nQuery: {q}"
        ),
    )


def _soil_city_state_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["q"],
        template=(
            "Extract the city and state from the user's query if present. "
            "Return ONLY valid JSON with keys: city, state (title case strings or null).\n"
            "{\n  \"city\": <string|null>,\n  \"state\": <string|null>\n}\n\nQuery: {q}"
        ),
    )


async def _geocode_region(name: str) -> Tuple[Optional[float], Optional[float]]:
    """Geocode a freeform region string using OpenWeather Geo API first, then Nominatim as fallback."""
    q = (name or "").strip()
    if not q:
        return None, None
    # Try OpenWeather direct geocoding
    try:
        if config.OPENWEATHER_API_KEY:
            async with httpx.AsyncClient(timeout=10) as client:
                # OWM Geo API: q can be "city,state,country"
                params = {"q": q, "limit": 1, "appid": config.OPENWEATHER_API_KEY}
                resp = await client.get("https://api.openweathermap.org/geo/1.0/direct", params=params)
                if resp.status_code == 200:
                    arr = resp.json()
                    if isinstance(arr, list) and arr:
                        it = arr[0]
                        lat = it.get("lat")
                        lon = it.get("lon")
                        if lat is not None and lon is not None:
                            return float(lat), float(lon)
                else:
                    logger.info("OWM geocode failed: %s", resp.text)
    except Exception as e:
        logger.info("OWM geocode exception: %s", e)
    # Fallback: Nominatim
    try:
        headers = {"User-Agent": "captial-one-agri-app/1.0"}
        params = {"q": q, "format": "json", "limit": 1}
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            resp = await client.get("https://nominatim.openstreetmap.org/search", params=params)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    item = data[0]
                    lat = float(item.get("lat"))
                    lon = float(item.get("lon"))
                    return lat, lon
            else:
                logger.warning("Nominatim geocode failed: %s", resp.text)
    except Exception as e:
        logger.warning("Nominatim geocode exception: %s", e)
    return None, None


async def plan_fetchers(query: str, body_lat: Optional[float] = None, body_lon: Optional[float] = None, body_region: Optional[str] = None) -> Tuple[List[Tuple], str, List[str]]:
    """Decide which external fetchers to run for the given query.
    Returns (fetchers, prompt_key, picked_ids)
    where fetchers is a list of (callable, args_dict).
    """
    # Local import to avoid static resolver issues in some environments
    try:
        from routers.pipelines.uv import fetch_uv_data  # type: ignore
    except Exception:
        fetch_uv_data = None  # type: ignore
    picked_defs = select_pipelines(query)
    picked_ids = [p.id for p in picked_defs]

    # Determine coordinates priority: request body > region geocode > LLM > regex
    lat = body_lat
    lon = body_lon
    source = "body" if (lat is not None and lon is not None) else None
    extracted_region: Optional[str] = None
    if source == "body":
        logger.info("Planner using body coords lat=%s lon=%s", lat, lon)
    # If body missing, try explicit body_region then region extraction + geocode
    if lat is None or lon is None:
        # Prefer body_region if present
        if body_region and isinstance(body_region, str) and body_region.strip():
            extracted_region = body_region.strip()
            lat_g, lon_g = await _geocode_region(body_region)
            if lat_g is not None and lon_g is not None:
                lat, lon = lat_g, lon_g
                source = f"geocode:{body_region}"
        if lat is None or lon is None:
            try:
                raw = run_chain(_region_extraction_prompt(), {"q": query})
                obj = json.loads(raw)
                region = obj.get("region") if isinstance(obj, dict) else None
                if isinstance(region, str) and region.strip():
                    extracted_region = region.strip()
                    lat_g, lon_g = await _geocode_region(region)
                    if lat_g is not None and lon_g is not None:
                        lat, lon = lat_g, lon_g
                        source = f"geocode:{region}"
            except Exception:
                pass
    # If still missing, try LLM coord extraction
    if lat is None or lon is None:
        try:
            raw = run_chain(_latlon_extraction_prompt(), {"q": query})
            obj = json.loads(raw)
            lat = obj.get("lat")
            lon = obj.get("lon")
            source = source or "llm"
        except Exception:
            pass
    if lat is None or lon is None:
        import re
        nums = re.findall(r"[-+]?\d{1,3}(?:\.\d+)?", query)
        if len(nums) >= 2:
            try:
                a = float(nums[0])
                b = float(nums[1])
                # Heuristic: pick lat in [-90,90], lon in [-180,180]
                cand = None
                if -90.0 <= a <= 90.0 and -180.0 <= b <= 180.0:
                    cand = (a, b)
                elif -90.0 <= b <= 90.0 and -180.0 <= a <= 180.0:
                    cand = (b, a)
                if cand:
                    lat, lon = cand
                    source = source or "regex"
            except Exception:
                pass
    # If still missing but a location-based pipeline is selected, use hardcoded defaults
    needs_coords = any(pid in ("weather_advice", "soil_advice", "uv_advice", "irrigation_advice") for pid in picked_ids)
    if (lat is None or lon is None) and needs_coords:
        lat = 18.3677
        lon = 73.77395
        source = source or "default"
    logger.info("Planner coords -> lat=%s lon=%s (source=%s)", lat, lon, source)

    fetchers: List[Tuple] = []
    added = set()
    for p in picked_defs:
        if p.id == "weather_advice" and lat is not None and lon is not None:
            key = ("weather", float(lat), float(lon))
            if key not in added:
                fetchers.append((fetch_weather_data, {"lat": float(lat), "lon": float(lon)}))
                added.add(key)
        elif p.id == "soil_advice":
            # Always extract city/state using LLM
            city_hint: Optional[str] = None
            state_hint: Optional[str] = None
            try:
                raw = run_chain(_soil_city_state_prompt(), {"q": query})
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    c = obj.get("city")
                    s = obj.get("state")
                    city_hint = c.title() if isinstance(c, str) and c else None
                    state_hint = s.title() if isinstance(s, str) and s else None
            except Exception:
                pass
            key = ("soil", state_hint or "", city_hint or "")
            if key not in added:
                fetchers.append((fetch_soil_data, {"state": state_hint, "district": city_hint, "limit": 10, "offset": 0}))
                added.add(key)
        elif p.id == "uv_advice" and lat is not None and lon is not None:
            key = ("uv", float(lat), float(lon))
            if key not in added:
                fetchers.append((fetch_uv_data, {"lat": float(lat), "lon": float(lon)}))
                added.add(key)
        elif p.id == "mandi_advice":
            fetchers.append((fetch_mandi_data_from_query, {"question": query}))

    # If irrigation is selected, prefer to fetch both weather and soil if coords exist
    if "irrigation_advice" in picked_ids and lat is not None and lon is not None:
        if ("weather", float(lat), float(lon)) not in added:
            fetchers.append((fetch_weather_data, {"lat": float(lat), "lon": float(lon)}))
            added.add(("weather", float(lat), float(lon)))
        if not any(f is fetch_soil_data for f, _ in fetchers):
            # Try to derive coarse state/district for irrigation too
            state_hint = None
            district_hint = None
            region_src = extracted_region or (body_region if isinstance(body_region, str) else None)
            if isinstance(region_src, str) and "," in region_src:
                parts = [s.strip() for s in region_src.split(",") if s.strip()]
                if len(parts) >= 2:
                    district_hint = parts[0].title()
                    state_hint = parts[1].title()
            fetchers.append((fetch_soil_data, {"state": state_hint, "district": district_hint, "limit": 10, "offset": 0}))
            added.add(("soil", state_hint or "", district_hint or ""))

    if not fetchers:
        logger.warning("Planner: no fetchers added (coords missing=%s or pipelines only-doc)", lat is None or lon is None)

    # Prompt key: prefer irrigation if irrigation pipeline is selected or both weather+soil are needed; otherwise from first picked weather/soil
    has_weather = "weather_advice" in picked_ids
    has_soil = "soil_advice" in picked_ids
    prompt_key = next((p.prompt_key for p in picked_defs if p.id in ("weather_advice", "soil_advice")), picked_defs[0].prompt_key)
    if ("irrigation_advice" in picked_ids) or (has_weather and has_soil):
        prompt_key = "irrigation"
    logger.info("Planner picked=%s prompt_key=%s fetchers=%d", ",".join(picked_ids), prompt_key, len(fetchers))
    return fetchers, prompt_key, picked_ids
