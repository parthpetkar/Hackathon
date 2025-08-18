from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
from typing import Optional
from datetime import datetime, timezone
import json
from api.pipeline_selector import plan_fetchers
from .pipelines.common import run_multi_pipeline
from config import config

router = APIRouter()
logger = logging.getLogger("rag")


class QueryRequest(BaseModel):
    transcription: Optional[str] = Field(default=None, description="Transcribed query text")
    query: Optional[str] = Field(default=None, description="Single query string")
    call_sid: str = Field(..., description="Unique Call SID for grouping history")
    lat: Optional[float] = Field(default=None, description="Latitude (optional)")
    lon: Optional[float] = Field(default=None, description="Longitude (optional)")


# Pipeline endpoints live in routers/pipelines.py


@router.post("/response")
async def response(payload: QueryRequest):
    # Validate inputs (single query mode)
    question = payload.query or payload.transcription
    if not question:
        raise HTTPException(status_code=400, detail="Provide 'transcription' or 'query'")

    try:
        # Plan fetchers and prompt based on the query
        fetchers, prompt_key, picked_ids = await plan_fetchers(question, body_lat=payload.lat, body_lon=payload.lon)
        logger.info("Planned fetchers=%d picked=%s", len(fetchers), ",".join(picked_ids))
        result = await run_multi_pipeline(question, prompt_key=prompt_key, fetchers=fetchers)
        sim = 1.0
        output_text = result.get("output") if isinstance(result, dict) else str(result)
        logger.info("Generated output length: %d chars", len(output_text or ""))

        # Save interaction in Redis (non-fatal if it fails)
        try:
            rec = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "query": question,
                "response": output_text,
                "similarity": sim,
            }
            if len(picked_ids) > 1:
                rec["pipelines"] = picked_ids
            else:
                rec["pipeline"] = picked_ids[0] if picked_ids else "unknown"
            key = f"call:{payload.call_sid}:history"
            config.redis_client.lpush(key, json.dumps(rec).encode("utf-8"))
        except Exception as e:
            logger.error("Redis save failed for %s: %s", payload.call_sid, e)

        resp = {"output": output_text, "similarity": sim, "call_sid": payload.call_sid}
        if len(picked_ids) > 1:
            resp["pipelines"] = picked_ids
        else:
            resp["pipeline"] = picked_ids[0] if picked_ids else "unknown"
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG failed: {str(e)}")