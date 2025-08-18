import json
import os
import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config import config
from routers.retrieval import get_embeddings
from langchain_redis import RedisVectorStore
from langchain_core.documents import Document

logger = logging.getLogger("pipeline_selector")

try:
    # Use cosine_similarity provided by langchain_redis vectorstores (optional for scoring output)
    from langchain_redis.vectorstores import (
        cosine_similarity as lc_cosine_similarity,  # type: ignore
    )
except Exception:
    lc_cosine_similarity = None  # scoring will rely on store if available


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

_PIPELINE_EMBED_HASH = "pipelines:v1:embeds"  # no longer used for storage, kept for backward compat (ignored)
_QUERY_EMBED_PREFIX = "embed:query:v1:"

# Fallback in-memory caches if Redis unavailable
_memory_pipeline_embeds: Dict[str, List[float]] = {}
_memory_query_embeds: Dict[str, List[float]] = {}

_PIPELINES_CACHE: Optional[List[PipelineDef]] = None


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _cosine(a: List[float], b: List[float]) -> float:
    if lc_cosine_similarity is None:
        return 0.0
    aa = [a]
    bb = [b]
    sim_mat = lc_cosine_similarity(aa, bb)
    try:
        return float(sim_mat[0][0])
    except Exception:
        return float(sim_mat)


def _redis_safe_set(key: str, value: bytes) -> None:
    try:
        config.redis_client.set(key, value)
    except Exception as e:
        logger.warning(f"Redis SET failed: {e}")


def _redis_safe_get(key: str) -> Optional[bytes]:
    try:
        return config.redis_client.get(key)
    except Exception as e:
        logger.warning(f"Redis GET failed: {e}")
        return None


def load_pipelines() -> List[PipelineDef]:
    global _PIPELINES_CACHE
    if _PIPELINES_CACHE is not None:
        return _PIPELINES_CACHE

    # Strictly require JSON file; no defaults
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
    return _PIPELINES_CACHE


def _get_pipeline_vector_store() -> RedisVectorStore:
    embeddings = get_embeddings()
    vs = RedisVectorStore(
        embeddings=embeddings,
        index_name=config.PIPELINE_INDEX_NAME,
        redis_url=config.REDIS_URL,
        metadata_schema=[
            {"name": "pipeline_id", "type": "tag"},
            {"name": "prompt_key", "type": "text"},
        ],
    )
    return vs


def ensure_pipeline_index() -> None:
    """Ensure pipeline descriptions are indexed as vectors in RedisVectorStore."""
    pipelines = load_pipelines()
    if not pipelines:
        return
    vs = _get_pipeline_vector_store()
    docs: List[Document] = []
    ids: List[str] = []
    for p in pipelines:
        docs.append(
            Document(
                page_content=_normalize_text(p.description),
                metadata={"pipeline_id": p.id, "prompt_key": p.prompt_key},
            )
        )
        ids.append(p.id)
    # Upsert by providing stable IDs; repeated calls overwrite vectors
    vs.add_documents(docs, ids=ids)


def get_query_embedding(text: str) -> List[float]:
    key = _QUERY_EMBED_PREFIX + hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()

    # Redis cache first
    raw = _redis_safe_get(key)
    if raw:
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            pass

    # Memory cache
    if key in _memory_query_embeds:
        return _memory_query_embeds[key]

    # Compute and cache
    vec = get_embeddings().embed_query(_normalize_text(text))
    payload = json.dumps(vec).encode("utf-8")
    _redis_safe_set(key, payload)
    _memory_query_embeds[key] = vec
    return vec


def select_pipeline(query: str) -> Tuple[PipelineDef, float]:
    """Return the best pipeline and its similarity score."""
    pipelines = load_pipelines()
    if not pipelines:
        raise RuntimeError("No pipelines loaded. Ensure pipelines.json is configured.")
    if not query:
        # Fallback to last pipeline (commonly general)
        return pipelines[-1], 0.0

    # Ensure vectors are present in the pipeline index
    ensure_pipeline_index()

    # Use retriever on the pipeline vector index
    vs = _get_pipeline_vector_store()
    retriever = vs.as_retriever(search_kwargs={"k": 1})
    docs = retriever.get_relevant_documents(query)

    if not docs:
        # As a final fallback, pick the last pipeline
        return pipelines[-1], 0.0

    top = docs[0]
    pid = (top.metadata or {}).get("pipeline_id")
    pkey = (top.metadata or {}).get("prompt_key")
    # Map back to declared pipeline for a consistent object
    pmap = {p.id: p for p in pipelines}
    chosen = pmap.get(pid, pipelines[-1])

    # Optionally compute similarity (for reporting) using cached query embedding
    sim = 0.0
    if lc_cosine_similarity is not None:
        try:
            q_vec = get_query_embedding(query)
            # Compute p_vec by embedding the description once
            p_vec = _memory_pipeline_embeds.get(chosen.id)
            if p_vec is None:
                p_vec = get_embeddings().embed_query(_normalize_text(chosen.description))
                _memory_pipeline_embeds[chosen.id] = p_vec
            sim = _cosine(q_vec, p_vec)
        except Exception:
            sim = 0.0

    return chosen, float(sim)
