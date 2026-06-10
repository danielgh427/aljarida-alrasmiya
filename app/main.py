"""Thin FastAPI application — only route handlers and startup wiring."""
from __future__ import annotations

import sys
import os
import threading
import logging

from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import uvicorn
import chromadb
from openai import OpenAI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import VECTOR_DB_PATH
from app.schemas.request import QuestionRequest
from app.services.rag_pipeline import RagPipeline
from app.database.db_connection import connect_db

logger = logging.getLogger(__name__)

# ── Lazy embedding model wrapper ─────────────────────────────────────

class _LazyEmbeddingModel:
    """Wraps SentenceTransformer and loads it on first use.

    The model is downloaded/loaded in a background thread at startup so
    the process is ready to serve health checks immediately.  Any call to
    ``encode`` before the model is ready will block only that request
    until loading finishes.
    """

    MODEL_NAME = "intfloat/multilingual-e5-base"

    def __init__(self) -> None:
        self._model = None
        self._lock  = threading.Lock()
        self._ready = threading.Event()
        self._error: Exception | None = None

    # Called by the lifespan to kick off background loading
    def load_in_background(self) -> None:
        t = threading.Thread(target=self._load, daemon=True, name="model-loader")
        t.start()

    def _load(self) -> None:
        try:
            logger.info("Loading embedding model %s …", self.MODEL_NAME)
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(self.MODEL_NAME)
            with self._lock:
                self._model = model
            logger.info("Embedding model loaded successfully.")
        except Exception as exc:
            logger.exception("Failed to load embedding model: %s", exc)
            self._error = exc
        finally:
            self._ready.set()

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set() and self._error is None

    @property
    def is_loading(self) -> bool:
        return not self._ready.is_set()

    def encode(self, *args, **kwargs):
        # Block until the model is available (or failed)
        self._ready.wait()
        if self._error is not None:
            raise RuntimeError(
                f"Embedding model failed to load: {self._error}"
            ) from self._error
        return self._model.encode(*args, **kwargs)  # type: ignore[union-attr]


# Module-level singletons — populated inside the lifespan
_lazy_model: _LazyEmbeddingModel | None = None
_pipeline:   RagPipeline | None = None


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _lazy_model, _pipeline

    # Fast, synchronous initialisation (DB + vector store + OpenAI client)
    db_conn    = connect_db()
    db_cursor  = db_conn.cursor(dictionary=True)

    chroma_cli = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    collection = chroma_cli.get_or_create_collection("rag_collection")

    openai_client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    # Kick off heavy model loading in the background
    _lazy_model = _LazyEmbeddingModel()
    _lazy_model.load_in_background()

    _pipeline = RagPipeline(
        mysql_cursor      = db_cursor,
        chroma_model      = _lazy_model,
        chroma_collection = collection,
        openai_client     = openai_client,
        vector_db_path    = VECTOR_DB_PATH,
    )

    logger.info("Startup complete — embedding model loading in background.")
    yield

    # Graceful shutdown (nothing heavy to tear down)
    logger.info("Shutting down.")


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
    """Always returns 200 — used by Railway's health check."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Returns 200 when the embedding model is fully loaded, 503 while loading."""
    if _lazy_model is None or _lazy_model.is_loading:
        return JSONResponse(
            status_code=503,
            content={"status": "loading", "message": "Embedding model is still loading."},
        )
    if _lazy_model._error is not None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Embedding model failed to load."},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ready", "message": "All systems operational."},
    )


@app.post("/ask")
async def ask(request: QuestionRequest) -> dict[str, object]:
    if _pipeline is None:
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={"error": "Service is still starting up. Please try again shortly."},
        )
    if _lazy_model is not None and _lazy_model.is_loading:
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={
                "answer": "النموذج لا يزال يُحمَّل، يرجى المحاولة مرة أخرى بعد لحظات.",
                "sources": [],
                "detected_category": request.category or "law",
            },
        )
    return await _pipeline.ask(request)


# ── Static Files — MUST BE LAST ──────────────────────────────────────
frontend_dir = os.path.join(os.getcwd(), "Frontend")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ── Entry-point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)