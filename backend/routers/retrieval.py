# retrieval.py
from langchain_redis import RedisVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from config import config
import logging

logger = logging.getLogger("retrieval")

model_kwargs = {"device": config.EMBEDDING_DEVICE}
if config.EMBEDDING_DEVICE == "cuda":
    import torch
    torch.backends.cudnn.benchmark = True
_embeddings = HuggingFaceEmbeddings(
    model_name=config.EMBEDDING_MODEL,
    model_kwargs=model_kwargs
)
_vector_store = None

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        try:
            _vector_store = RedisVectorStore.from_existing_index(
                embedding=_embeddings,
                index_name=config.REDIS_INDEX_NAME,
                redis_url=config.REDIS_URL,
            )
            logger.info("Connected to Redis vector store")
        except Exception as e:
            logger.error(f"Vector store connection failed: {str(e)}")
            raise RuntimeError("Vector store unavailable")
    return _vector_store

def get_embeddings():
    """Expose the shared embedding model for other services to reuse."""
    return _embeddings