from fastapi import FastAPI
import logging, os
from routers.api import router as rag_router
from routers.ingest import router as ingest_router
from api.pipeline_selector import ensure_pipeline_index

# Configure basic logging; override with LOG_LEVEL env var
_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _level, logging.INFO), format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

app = FastAPI()
# Expose routes without a prefix so paths are exactly "/response" and "/ingest"
app.include_router(rag_router)
app.include_router(ingest_router)


@app.on_event("startup")
async def _warm_pipeline_cache():
	# Precompute and cache pipeline description embeddings
	try:
		ensure_pipeline_index()
	except Exception:
		# Non-fatal; selection will compute on-demand
		pass
