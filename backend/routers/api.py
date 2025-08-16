from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
import asyncio
from typing import List, Optional
from datetime import datetime, timezone
import json
from api.common import run_chain, get_prompt_template, format_docs
from routers.retrieval import get_vector_store
from config import config

router = APIRouter()
logger = logging.getLogger("rag")


class QueryRequest(BaseModel):
    transcription: Optional[str] = Field(default=None, description="Transcribed query text")
    query: Optional[str] = Field(default=None, description="Single query string")
    queries: Optional[List[str]] = Field(default=None, description="List of queries")
    call_sid: str = Field(..., description="Unique Call SID for grouping history")


async def answer_query(question: str):
    try:
        vector_store = get_vector_store()
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": 4,
                "score_threshold": 0.6,
            }
        )
        docs = retriever.get_relevant_documents(question)
        context = format_docs(docs)
        prompt = get_prompt_template("generation")
        answer = run_chain(prompt, {"context": context, "question": question})
        return answer
    except Exception as e:
        logger.error(f"Query failed: {str(e)}")
        raise


@router.post("/response")
async def response(payload: QueryRequest):
    # Validate inputs
    question = payload.query or payload.transcription
    if not question and not payload.queries:
        raise HTTPException(status_code=400, detail="Provide 'transcription' or 'query' or 'queries'")

    if question and payload.queries:
        raise HTTPException(status_code=400, detail="Provide only one of single 'query/transcription' or 'queries'")

    try:
        if question:
            ans = await answer_query(question)
            # Save interaction in Redis (non-fatal if it fails)
            try:
                rec = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "query": question,
                    "response": ans,
                }
                key = f"call:{payload.call_sid}:history"
                config.redis_client.lpush(key, json.dumps(rec).encode("utf-8"))
            except Exception as e:
                logger.error(f"Redis save failed for {payload.call_sid}: {e}")
            return {"output": ans, "call_sid": payload.call_sid}
        else:
            qs = payload.queries or []
            tasks = [answer_query(q) for q in qs]
            answers = await asyncio.gather(*tasks)
            # Save each interaction
            try:
                key = f"call:{payload.call_sid}:history"
                now = datetime.now(timezone.utc).isoformat()
                pipe = config.redis_client.pipeline()
                for q, a in zip(qs, answers):
                    rec = {"ts": now, "query": q, "response": a}
                    pipe.lpush(key, json.dumps(rec).encode("utf-8"))
                pipe.execute()
            except Exception as e:
                logger.error(f"Redis batch save failed for {payload.call_sid}: {e}")
            return {"output": answers, "call_sid": payload.call_sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG failed: {str(e)}")