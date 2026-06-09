"""Thin FastAPI application — only route handlers and startup wiring.

Business logic lives in:
  - app/services/helpers.py          (pure utilities)
  - app/services/rag_pipeline.py     (orchestration + dependencies)
  - app/schemas/                     (Pydantic DTOs)
  - app/database/                    (MySQL connection factory)
"""
from __future__ import annotations

import sys
import os

from dotenv import load_dotenv
load_dotenv()

os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import uvicorn
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ── Project root on sys.path ─────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import VECTOR_DB_PATH                    # noqa: E402
from app.schemas.request import QuestionRequest      # noqa: E402
from app.services.rag_pipeline import RagPipeline    # noqa: E402
from app.database.db_connection import connect_db    # noqa: E402


# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(title="Lebanese Law & Tenders Robust RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Warm-start dependencies ──────────────────────────────────────────
_db_conn    = connect_db()
_model      = SentenceTransformer("intfloat/multilingual-e5-base")
_chroma_cli = chromadb.PersistentClient(path=VECTOR_DB_PATH)
_collection = _chroma_cli.get_or_create_collection("rag_collection")

_openai = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

_DB_CURSOR = _db_conn.cursor(dictionary=True)

pipeline = RagPipeline(
    mysql_cursor      = _DB_CURSOR,
    chroma_model      = _model,
    chroma_collection = _collection,
    openai_client     = _openai,
    vector_db_path    = VECTOR_DB_PATH,
)


# ── Routes ───────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask")
async def ask(request: QuestionRequest) -> dict[str, object]:
    """
    Ask a question about Lebanese laws or tenders.
    Access via: POST http://localhost:8000/ask
    Or use Swagger UI at: http://localhost:8000/docs
    """
    return await pipeline.ask(request)


# ── Static Files — MUST BE LAST ──────────────────────────────────────
# ── Static Files — MUST BE LAST ──────────────────────────────────────
frontend_dir = os.path.join(os.getcwd(), "Frontend")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "error": "Frontend not found",
            "looked_in": frontend_dir,
            "cwd": os.getcwd()
        }


# ── Entry-point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)