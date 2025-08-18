import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .common import run_pipeline

router = APIRouter()
logger = logging.getLogger("pipelines.general")


class GeneralQuery(BaseModel):
    query: str = Field(...)


@router.post("/pipeline/general")
async def pipeline_general(payload: GeneralQuery):
    try:
        result = await run_pipeline(payload.query, prompt_key="general")
        result["pipeline"] = "general_assistant"
        return result
    except Exception as e:
        logger.exception("General pipeline failed")
        raise HTTPException(status_code=500, detail=f"General pipeline failed: {str(e)}")
