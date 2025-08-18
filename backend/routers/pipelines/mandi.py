import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
import json
import httpx

from .common import run_pipeline, get_prompt_key_for_pipeline
from api.common import run_chain
from langchain.prompts import PromptTemplate
from config import config

router = APIRouter()
logger = logging.getLogger("pipelines.mandi")

DATA_GOV_RESOURCE_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"


class MandiQuery(BaseModel):
    query: str = Field(...)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


async def fetch_mandi_data(
    *,
    state: Optional[str] = None,
    district: Optional[str] = None,
    market: Optional[str] = None,
    commodity: Optional[str] = None,
    variety: Optional[str] = None,
    grade: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    api_key = config.DATA_GOV_API_KEY
    params: dict[str, Any] = {
        "api-key": api_key,
        "format": "json",
    "limit": limit,
    "offset": offset,
    }
    # Add filters if provided
    def add_filter(key: str, val: Optional[str]):
        if val:
            params[f"filters[{key}]"] = val

    add_filter("state.keyword", state)
    add_filter("district", district)
    add_filter("market", market)
    add_filter("commodity", commodity)
    add_filter("variety", variety)
    add_filter("grade", grade)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(DATA_GOV_RESOURCE_URL, params=params)
        if resp.status_code != 200:
            logger.error(f"Mandi API failed: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=502, detail="Failed to fetch mandi prices")
        data = resp.json()
        records = data.get("records") or []
        total = data.get("total") or len(records)
        return {"mandi_records": records, "total": total}


def _get_extraction_prompt() -> PromptTemplate:
    return PromptTemplate(
        input_variables=["question"],
        template=(
            "You extract structured filters from a user query about Indian mandi prices.\n"
            "Return ONLY valid JSON with these keys: state, district, market, commodity, variety, grade, limit, offset.\n"
            "- Use title case strings (e.g., 'Maharashtra', 'Pune').\n"
            "- If a field is not present, set it to null.\n"
            "- If the user mentions a number of results or pagination, set limit/offset as integers; otherwise null.\n"
            "- Do not add explanations.\n\n"
            "Query: {question}\n"
        ),
    )


def _extract_filters_from_query(query: str) -> dict[str, Any]:
    try:
        raw = run_chain(_get_extraction_prompt(), {"question": query})
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        # Normalize keys to lowercase and map synonyms
        def norm_key(k: Any) -> str:
            return str(k).strip().lower()

        canonical = {
            "state": None,
            "district": None,
            "market": None,
            "commodity": None,
            "variety": None,
            "grade": None,
            "limit": None,
            "offset": None,
        }
        synonyms = {
            "state.keyword": "state",
            "mandi": "market",
            "market_name": "market",
            "city": "district",
        }

        for k, v in data.items():
            nk = norm_key(k)
            target = synonyms.get(nk, nk)
            if target in canonical:
                canonical[target] = v

        logger.debug("Mandi filters extracted raw=%s normalized=%s", data, canonical)
        return canonical
    except Exception:
        return {}


async def run_mandi_pipeline(question: str, *, default_limit: int = 10, default_offset: int = 0) -> dict:
    filters = _extract_filters_from_query(question)
    # Coerce and fallback
    def _clean_str(v):
        if not isinstance(v, str):
            return None
        s = v.strip()
        if not s:
            return None
        if s.lower() in {"not specified", "na", "n/a", "none", "null", "-", "unknown"}:
            return None
        return s
    def _clean_int(v, default):
        try:
            return int(v)
        except Exception:
            return default

    def _clean_name(v):
        s = _clean_str(v)
        return s.title() if s else None

    fetch_args = {
        "state": _clean_name(filters.get("state")),
        "district": _clean_name(filters.get("district")),
        "market": _clean_name(filters.get("market")),
        "commodity": _clean_name(filters.get("commodity")),
        "variety": _clean_name(filters.get("variety")),
        "grade": _clean_str(filters.get("grade")),
        "limit": _clean_int(filters.get("limit"), default_limit),
        "offset": _clean_int(filters.get("offset"), default_offset),
    }
    prompt_key = get_prompt_key_for_pipeline("mandi_advice", default="general")
    return await run_pipeline(
        question,
        prompt_key=prompt_key,
        external_fetcher=fetch_mandi_data,
        fetcher_args=fetch_args,
    )


@router.post("/pipeline/mandi")
async def pipeline_mandi(payload: MandiQuery):
    try:
        result = await run_mandi_pipeline(
            payload.query,
            default_limit=payload.limit,
            default_offset=payload.offset,
        )
        result["pipeline"] = "mandi_advice"
        return result
    except Exception as e:
        logger.exception("Mandi pipeline failed")
        raise HTTPException(status_code=500, detail=f"Mandi pipeline failed: {str(e)}")
