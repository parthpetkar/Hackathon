import torch
# config.py
import os
import redis
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"
    REDIS_INDEX_NAME = "pdf_vectors"
    PIPELINE_INDEX_NAME = os.getenv("PIPELINE_INDEX_NAME", "pipeline_vectors")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME")
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    AGRO_API_KEY = os.getenv("AGRO_API_KEY")
    DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY")
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    GPU_ENABLED = os.getenv("GPU_ENABLED", "true").lower() == "true"
    print(f"Using GPU: {GPU_ENABLED}")
    EMBEDDING_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    EMBEDDING_BATCH_SIZE = 128 if EMBEDDING_DEVICE == "cuda" else 16
    INGEST_BATCH_SIZE = 500
    RERANK_BATCH_SIZE = 64
    
    # Initialize Redis connection pool
    redis_pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        max_connections=20,
        decode_responses=False
    )
    
    @property
    def redis_client(self):
        return redis.Redis(connection_pool=self.redis_pool)

config = Config()