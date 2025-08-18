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
from routers.pipelines.uv import fetch_uv_data
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


def _routing_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["pipelines", "question"],
        template=(
            "You are an expert router that maps a user query to the best pipeline.\n"
            "You are given a list of pipelines as JSON objects with fields: id, description, prompt_key.\n"
            "Choose exactly ONE pipeline id that best fits the query intent.\n"
            "Respond ONLY with a JSON object of the form:\n"
            "{{\n  \"pipeline_id\": \"<one of the ids listed>\",\n  \"reason\": \"short rationale\"\n}}\n\n"
            "Pipelines:\n{pipelines}\n\n"
            "Query:\n{question}"
        ),
    )


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
        logger.warning("Failed to parse multi-route output; falling back to single route")
    # Fallback to single route
    single, _ = select_pipeline(query)
    logger.info("Fallback selected pipeline: %s", single.id)
    return [single]


def _safe_json_find_id(text: str, valid_ids: List[str]) -> Optional[str]:
    # Try strict JSON parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            pid = obj.get("pipeline_id") or obj.get("id")
            if isinstance(pid, str) and pid in valid_ids:
                return pid
    except Exception:
        pass
    # Fallback: scan for any valid id token appearance
    for pid in valid_ids:
        if pid in text:
            return pid
    return None


def select_pipeline(query: str) -> Tuple[PipelineDef, float]:
    pipelines = load_pipelines()
    if not pipelines:
        raise RuntimeError("No pipelines loaded. Ensure pipelines.json is configured.")
    if not query:
        return pipelines[-1], 0.0

    plist = [
        {"id": p.id, "description": p.description, "prompt_key": p.prompt_key}
        for p in pipelines
    ]
    prompt = _routing_prompt()
    logger.info("Routing single pipeline for query: %s", query)
    llm_out = run_chain(prompt, {"pipelines": json.dumps(plist, ensure_ascii=False), "question": query})
    logger.debug("Single-route LLM output: %s", llm_out)

    valid_ids = [p.id for p in pipelines]
    chosen_id = _safe_json_find_id(llm_out, valid_ids)
    id_to_def: Dict[str, PipelineDef] = {p.id: p for p in pipelines}
    chosen = id_to_def.get(chosen_id or "", pipelines[-1])
    logger.info("Selected pipeline: %s", chosen.id)

    # Return a nominal confidence of 1.0 for LLM routing
    return chosen, 1.0


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


async def _geocode_region(name: str) -> Tuple[Optional[float], Optional[float]]:
    try:
        headers = {"User-Agent": "captial-one-agri-app/1.0"}
        params = {"q": name, "format": "json", "limit": 1}
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            resp = await client.get("https://nominatim.openstreetmap.org/search", params=params)
            if resp.status_code != 200:
                logger.warning("Geocode failed: %s", resp.text)
                return None, None
            data = resp.json()
            if isinstance(data, list) and data:
                item = data[0]
                lat = float(item.get("lat"))
                lon = float(item.get("lon"))
                return lat, lon
    except Exception as e:
        logger.warning("Geocode exception: %s", e)
    return None, None


async def plan_fetchers(query: str, body_lat: Optional[float] = None, body_lon: Optional[float] = None) -> Tuple[List[Tuple], str, List[str]]:
    """Decide which external fetchers to run for the given query.
    Returns (fetchers, prompt_key, picked_ids)
    where fetchers is a list of (callable, args_dict).
    """
    picked_defs = select_pipelines(query)
    picked_ids = [p.id for p in picked_defs]

    # Determine coordinates priority: request body > region geocode > LLM > regex
    lat = body_lat
    lon = body_lon
    source = "body" if (lat is not None and lon is not None) else None
    if source == "body":
        logger.info("Planner using body coords lat=%s lon=%s", lat, lon)
    # If body missing, try region extraction + geocode
    if lat is None or lon is None:
        try:
            raw = run_chain(_region_extraction_prompt(), {"q": query})
            obj = json.loads(raw)
            region = obj.get("region") if isinstance(obj, dict) else None
            if isinstance(region, str) and region.strip():
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
        elif p.id == "soil_advice" and lat is not None and lon is not None:
            key = ("soil", float(lat), float(lon))
            if key not in added:
                fetchers.append((fetch_soil_data, {"lat": float(lat), "lon": float(lon)}))
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
        if ("soil", float(lat), float(lon)) not in added:
            fetchers.append((fetch_soil_data, {"lat": float(lat), "lon": float(lon)}))
            added.add(("soil", float(lat), float(lon)))

    if not fetchers:
        logger.warning("Planner: no fetchers added (coords missing=%s or pipelines only-doc)", lat is None or lon is None)

    # Prompt key: irrigation for weather/soil; otherwise from first picked
    prompt_key = next((p.prompt_key for p in picked_defs if p.id in ("weather_advice", "soil_advice")), picked_defs[0].prompt_key)
    logger.info("Planner picked=%s prompt_key=%s fetchers=%d", ",".join(picked_ids), prompt_key, len(fetchers))
    return fetchers, prompt_key, picked_ids
