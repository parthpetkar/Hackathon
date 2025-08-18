from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
from typing import Optional
from datetime import datetime, timezone
import json
from api.pipeline_selector import select_pipeline
from .pipelines.common import run_pipeline
from config import config

router = APIRouter()
logger = logging.getLogger("rag")


class QueryRequest(BaseModel):
    transcription: Optional[str] = Field(default=None, description="Transcribed query text")
    query: Optional[str] = Field(default=None, description="Single query string")
    call_sid: str = Field(..., description="Unique Call SID for grouping history")


# Pipeline endpoints live in routers/pipelines.py


@router.post("/response")
async def response(payload: QueryRequest):
    # Validate inputs (single query mode)
    question = payload.query or payload.transcription
    if not question:
        raise HTTPException(status_code=400, detail="Provide 'transcription' or 'query'")

    try:
        # Decide pipeline using the pipeline vector retriever
        pipeline, sim = select_pipeline(question)
        # Run with the selected pipeline's prompt key (general/irrigation/etc.)
        result = await run_pipeline(question, prompt_key=pipeline.prompt_key)
        output_text = result.get("output") if isinstance(result, dict) else str(result)

        # Save interaction in Redis (non-fatal if it fails)
        try:
            rec = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "query": question,
                "response": output_text,
                "pipeline": pipeline.id,
                "similarity": sim,
            }
            key = f"call:{payload.call_sid}:history"
            config.redis_client.lpush(key, json.dumps(rec).encode("utf-8"))
        except Exception as e:
            logger.error(f"Redis save failed for {payload.call_sid}: {e}")

        return {"output": output_text, "pipeline": pipeline.id, "similarity": sim, "call_sid": payload.call_sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG failed: {str(e)}")