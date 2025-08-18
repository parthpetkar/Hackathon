# Backend (FastAPI) — Setup and API usage (Windows PowerShell)

This backend powers the IVR responses. It exposes two endpoints:

- POST `/response` — generates an answer for a user query using LLM, vector search, and optional external data
- POST `/ingest` — OCRs PDFs and ingests chunked text into a Redis vector store

## Prerequisites

- Python 3.10+
- Redis server running and reachable (defaults to `localhost:6379`)
- API keys for services you intend to use:
    - Mistral: `MISTRAL_API_KEY` (required for LLM and OCR)
    - Agromonitoring: `AGRO_API_KEY` (weather/soil/uv)
    - data.gov.in: `DATA_GOV_API_KEY` (mandi prices)

Note on PyTorch: `config.py` imports `torch` to detect GPU. If you don’t have PyTorch installed, install a CPU build or CUDA build compatible with your system. Example (CPU only):
 
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 1) Create and activate a virtual environment

```powershell
cd backend
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## 2) Configure environment variables

Create a `.env` in `backend/` or copy `.env.example` and fill values.

Required (typical):

- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- `MISTRAL_API_KEY`
- `MODEL_NAME` (e.g., `mistral-large-latest` or `open-mistral-7b`)

Optional:

- `AGRO_API_KEY`, `DATA_GOV_API_KEY`, `GPU_ENABLED` (true/false), `PIPELINE_INDEX_NAME`

Example `.env`:

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

MISTRAL_API_KEY=your_mistral_key
MODEL_NAME=mistral-large-latest

# Optional
GPU_ENABLED=true
AGRO_API_KEY=your_agromonitoring_key
DATA_GOV_API_KEY=your_datagov_key
```

## 3) Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
# If needed for your environment
# pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 4) Start the API server

```powershell
uvicorn app:app --reload --host 0.0.0.0 --port 5000
```
The IVR service expects the backend at <http://localhost:5000>.

## 5) Endpoints

### POST /response

Generates an answer based on the query, optional location (lat/lon or region), and retrieved docs.

Body (JSON):

```json
{
    "query": "When should I irrigate my sugarcane this week?",
    "call_sid": "test-123",
    "lat": 18.5204,
    "lon": 73.8567,
    "region": "Pune, Maharashtra, India"
}
```

Response (JSON):

```json
{
    "output": "...answer text...",
    "similarity": 1.0,
    "call_sid": "test-123",
    "pipeline": "irrigation_advice"
}
```

Notes:

- Provide either `query` or `transcription`.
- `call_sid` groups history; any string is accepted for testing.
- Location improves weather/soil/uv answers; the service can also infer rough coords from region text.

### POST /ingest

OCRs all PDFs in a folder and ingests chunked text into Redis.

Body (JSON):

```json
{
    "folder_path": "D:/data/pdfs",
    "recursive": true,
    "collection": "agri-guides"
}
```

Response (JSON):

```json
{
    "success": true,
    "ingested_files": 3,
    "total_files": 3,
    "total_chunks": 842,
    "details": [ { "file": "...", "success": true, "document_count": 310 } ]
}
```

Requirements for ingestion:

- `MISTRAL_API_KEY` must be set (uses Mistral OCR).
- Redis must be running and reachable.

## Troubleshooting

- Torch not installed: install a CPU/CUDA build of `torch`.
- Redis errors: ensure the server is running and env points to the correct host/port.
- External API failures: check `AGRO_API_KEY` and `DATA_GOV_API_KEY` if using weather/soil/uv/mandi features.
- GPU settings: `GPU_ENABLED` toggles preference; actual device is auto-detected (`cuda` if available, else `cpu`).

## Project structure

- App entry: `app.py` (FastAPI)
- Config: `config.py` (reads `.env`)
- RAG logic: `routers/` and `api/`
- Pipelines list: `api/pipelines.json`

Once running on port 5000, your IVR will call this backend at `POST /response` to get the spoken answer.
