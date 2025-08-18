from fastapi import FastAPI
from routers.api import router as rag_router
from routers.ingest import router as ingest_router
from routers.pipelines.general import router as general_pipeline_router
from routers.pipelines.weather import router as weather_pipeline_router
from routers.pipelines.soil import router as soil_pipeline_router
from routers.pipelines.uv import router as uv_pipeline_router
from api.pipeline_selector import ensure_pipeline_index

app = FastAPI()
# Expose routes without a prefix so paths are exactly "/response" and "/ingest"
app.include_router(rag_router)
app.include_router(ingest_router)
app.include_router(general_pipeline_router)
app.include_router(weather_pipeline_router)
app.include_router(soil_pipeline_router)
app.include_router(uv_pipeline_router)


@app.on_event("startup")
async def _warm_pipeline_cache():
	# Precompute and cache pipeline description embeddings
	try:
		ensure_pipeline_index()
	except Exception:
		# Non-fatal; selection will compute on-demand
		pass
