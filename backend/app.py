from fastapi import FastAPI
from routers.api import router as rag_router
from routers.ingest import router as ingest_router

app = FastAPI()
# Expose routes without a prefix so paths are exactly "/response" and "/ingest"
app.include_router(rag_router)
app.include_router(ingest_router)
