"""Thin FastAPI application — only route handlers and startup wiring."""
from __future__ import annotations

import sys
import os

from dotenv import load_dotenv
load_dotenv()

os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import uvicorn
import chromadb
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import VECTOR_DB_PATH
from app.schemas.request import QuestionRequest
from app.services.rag_pipeline import RagPipeline
from app.database.db_connection import connect_db
from app.database.init_db import init_db

# ── Module-level state (populated during lifespan startup) ───────────
_pipeline: RagPipeline | None = None
_db_ready: bool = False


# ── Lifespan: runs once before the server starts accepting requests ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline, _db_ready

    # 1. Ensure the database and tables exist before connecting
    try:
        init_db()
        _db_ready = True
    except Exception as exc:
        print(f"[startup] Database initialisation failed: {exc}")
        print("[startup] The /health endpoint will report degraded status.")

    # 2. Connect to MySQL (returns None on failure — pipeline degrades gracefully)
    db_conn = connect_db()
    db_cursor = db_conn.cursor(dictionary=True) if db_conn else None

    # 3. Load embedding model and vector store
    model      = SentenceTransformer("intfloat/multilingual-e5-base")
    chroma_cli = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    collection = chroma_cli.get_or_create_collection("rag_collection")

    # 4. OpenAI / OpenRouter client
    openai_client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    # 5. Build the pipeline only when a cursor is available
    if db_cursor is not None:
        _pipeline = RagPipeline(
            mysql_cursor      = db_cursor,
            chroma_model      = model,
            chroma_collection = collection,
            openai_client     = openai_client,
            vector_db_path    = VECTOR_DB_PATH,
        )
        print("[startup] RAG pipeline initialised successfully.")
    else:
        print("[startup] No database cursor — /ask will return a service-unavailable response.")

    yield  # ── application runs here ──────────────────────────────

    # Teardown: close the DB connection cleanly
    if db_conn and db_conn.is_connected():
        db_conn.close()
        print("[shutdown] MySQL connection closed.")


# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(title="Lebanese Law & Tenders Robust RAG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict[str, str]:
    """Always returns 200 so Railway's health checks pass.

    The ``db`` field reflects whether the database connection is live,
    allowing operators to distinguish a fully-ready instance from one
    that is still waiting for MySQL.
    """
    return {
        "status": "ok",
        "db":     "ready" if _db_ready and _pipeline is not None else "unavailable",
    }


@app.post("/ask")
async def ask(request: QuestionRequest) -> dict[str, object]:
    if _pipeline is None:
        return {
            "answer":            "الخدمة غير متاحة حالياً — قاعدة البيانات لم تتصل بعد. يرجى المحاولة لاحقاً.",
            "sources":           [],
            "detected_category": request.category or "law",
        }
    return await _pipeline.ask(request)


# ── Static Files — MUST BE LAST ──────────────────────────────────────
frontend_dir = os.path.join(os.getcwd(), "Frontend")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ── Entry-point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
