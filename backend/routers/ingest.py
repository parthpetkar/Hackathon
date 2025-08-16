import os
import logging
import hashlib
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from mistralai import Mistral
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_redis import RedisVectorStore
from config import config
from langchain_experimental.text_splitter import SemanticChunker

logger = logging.getLogger("ingestion")

# FastAPI router for ingestion
router = APIRouter()


class IngestRequest(BaseModel):
    folder_path: str = Field(..., description="Absolute or relative folder path containing PDFs")
    recursive: bool = Field(default=True, description="Recurse into subfolders")
    collection: str | None = Field(default=None, description="Optional collection name for metadata")

def get_text_splitter():
    embeddings = HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": config.EMBEDDING_DEVICE},
        encode_kwargs={
            "batch_size": config.EMBEDDING_BATCH_SIZE
        }
    )
    
    return SemanticChunker(
        embeddings,
        breakpoint_threshold_type="percentile",  # "standard_deviation", "interquartile"
        breakpoint_threshold_amount=0.5,
        min_chunk_size=1000
    )

def extract_text_with_mistral(file_path: str) -> str:
    """Fallback to Mistral OCR"""
    api_key = config.MISTRAL_API_KEY
    if not api_key:
        raise ValueError("MISTRAL_API_KEY is not configured")
    
    client = Mistral(api_key=api_key)
    filename = os.path.basename(file_path)
    
    try:
        with open(file_path, 'rb') as pdf_file:
            uploaded_file = client.files.upload(
                file={"file_name": filename, "content": pdf_file},
                purpose="ocr"
            )
        
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document_url", "document_url": signed_url.url}
        )
        
        # Structure OCR output with page markers
        structured_text = ""
        for i, page in enumerate(ocr_response.pages):
            structured_text += f"\n\n## PAGE_{i+1}_START\n{page.markdown}\n## PAGE_{i+1}_END\n"
        return structured_text
    
    except Exception as e:
        logger.error(f"Mistral OCR failed: {str(e)}")
        raise RuntimeError(f"OCR processing error: {str(e)}")
    finally:
        if 'uploaded_file' in locals():
            try:
                client.files.delete(file_id=uploaded_file.id)
            except Exception:
                pass

def ingest_pdf_internal(
    file_path: str,
    source_url: str,
    doc_hash: str,
    *,
    seen_chunk_hashes: set[str] | None = None,
    collection: str | None = None,
) -> dict:
    try:
        # Step 1: OCR Extraction
        extracted_text = extract_text_with_mistral(file_path)

        # Step 2: Create document from extracted text
        doc = Document(page_content=extracted_text, metadata={})

        # Step 3: Split document
        text_splitter = get_text_splitter()
        chunks = text_splitter.split_documents([doc])

        # Add metadata and optional dedup across files
        last_modified = os.path.getmtime(file_path)
        deduped_chunks = []
        if seen_chunk_hashes is None:
            seen_chunk_hashes = set()

        for chunk in chunks:
            chunk.metadata.update(
                {
                    "source": source_url,
                    "doc_hash": doc_hash,
                    "last_modified_time": last_modified,
                }
            )
            if collection:
                chunk.metadata["collection"] = collection

            norm_text = (chunk.page_content or "").strip().lower()
            h = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
            if h in seen_chunk_hashes:
                continue
            seen_chunk_hashes.add(h)
            deduped_chunks.append(chunk)

        # Create embeddings with GPU support
        model_kwargs = {"device": config.EMBEDDING_DEVICE}
        encode_kwargs = {"batch_size": config.EMBEDDING_BATCH_SIZE}
        embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )

        # Initialize vector store
        vector_store = RedisVectorStore(
            embeddings=embeddings,
            index_name=config.REDIS_INDEX_NAME,
            redis_url=config.REDIS_URL,
            metadata_schema=[
                {"name": "source", "type": "text"},
                {"name": "doc_hash", "type": "tag"},
                {"name": "last_modified_time", "type": "numeric"},
            ],
        )

        # Batch ingestion
        total_chunks = len(deduped_chunks)
        for i in range(0, total_chunks, config.INGEST_BATCH_SIZE):
            batch = deduped_chunks[i : i + config.INGEST_BATCH_SIZE]
            vector_store.add_documents(batch)
            logger.info(
                f"Ingested batch {i//config.INGEST_BATCH_SIZE + 1}/"
                f"{(total_chunks-1)//config.INGEST_BATCH_SIZE + 1}"
            )

        logger.info(f"Ingested {total_chunks} chunks into Redis")
        return {"success": True, "document_count": total_chunks}
    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        return {"success": False, "error": str(e)}


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

@router.post("/ingest")
async def ingest_endpoint(payload: IngestRequest):
    folder = payload.folder_path
    recursive = payload.recursive
    collection = payload.collection

    if not folder or not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail="folder_path must be an existing directory")

    # Collect PDF files
    pdf_files: list[str] = []
    if recursive:
        for root, _, files in os.walk(folder):
            for name in files:
                if name.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, name))
    else:
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            if os.path.isfile(p) and name.lower().endswith(".pdf"):
                pdf_files.append(p)

    if not pdf_files:
        raise HTTPException(status_code=400, detail="No PDF files found in folder")

    # Dedup state across this ingestion run
    seen_chunk_hashes: set[str] = set()

    results = []
    total_chunks = 0
    for path in pdf_files:
        try:
            # Compute hash based on file bytes
            with open(path, "rb") as f:
                content = f.read()
            doc_hash = _hash_bytes(content)

            res = ingest_pdf_internal(
                file_path=path,
                source_url=f"file://{os.path.abspath(path)}",
                doc_hash=doc_hash,
                seen_chunk_hashes=seen_chunk_hashes,
                collection=collection,
            )
            results.append({"file": path, **res})
            if res.get("success"):
                total_chunks += int(res.get("document_count", 0))
        except Exception as e:
            results.append({"file": path, "success": False, "error": str(e)})

    success_count = sum(1 for r in results if r.get("success"))
    return {
        "success": success_count == len(results),
        "ingested_files": success_count,
        "total_files": len(results),
        "total_chunks": total_chunks,
        "details": results,
    }