import sys
import os
import logging
import traceback
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 1. Load configuration
load_dotenv()
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import uvicorn
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# Setup professional logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AlJarida-Backend")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import VECTOR_DB_PATH
from app.schemas.request import QuestionRequest
from app.services.rag_pipeline import RagPipeline
from app.database.db_connection import connect_db

# ── LIFESPAN: Professional way to load heavy models ──
# This ensures the model is loaded before the server starts accepting traffic
_DEPENDENCIES = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⏳ Starting System Initialization...")
    
    # Load AI Model
    logger.info("⏳ Loading Embedding Model (multilingual-e5-small)...")
    model = SentenceTransformer("intfloat/multilingual-e5-small")
    _DEPENDENCIES["model"] = model
    
    # Initialize ChromaDB
    _chroma_cli = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    _collection = _chroma_cli.get_or_create_collection("rag_collection")
    _DEPENDENCIES["collection"] = _collection
    
    # OpenAI Client
    _openai = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    _DEPENDENCIES["openai"] = _openai
    
    logger.info("✅ Initialization Complete. Server is ready.")
    yield
    # Cleanup logic (if any) goes here
    logger.info("Shutting down...")

# ── FastAPI App Configuration ──
app = FastAPI(
    title="Al Jarida AI - Lebanese Law RAG",
    description="Professional Master's Project - Intelligent Legal Retrieval System",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
   CORSMiddleware,
   allow_origins=["*"], 
   allow_credentials=True,
   allow_methods=["*"],  
   allow_headers=["*"],
)

# ── GLOBAL EXCEPTION HANDLER: Professionalism ──
# Instead of showing the user a raw "EOF Error", show a clean JSON response
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"GLOBAL ERROR: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"answer": "عذراً، حدث خطأ فني في الاتصال. يرجى المحاولة مرة أخرى لاحقاً.", 
                 "detail": str(exc),
                 "sources": []}
    )

# ── ROUTES ──

@app.get("/health")
def health():
    return {"status": "ok", "environment": "production"}

@app.post("/ask")
async def ask(request: QuestionRequest):
    # CRITICAL CHANGE: Create a fresh connection per request
    # This ensures that if the DB dropped (EOF), we get a fresh pipe.
    db_conn = connect_db()
    if not db_conn:
        return JSONResponse(
            status_code=503,
            content={"answer": "قاعدة البيانات غير متوفرة حالياً بسبب ضغط على السيرفر.", "sources": []}
        )
    
    try:
        cursor = db_conn.cursor(dictionary=True)
        
        # Build pipeline with fresh cursor
        pipeline = RagPipeline(
            mysql_cursor=cursor,
            chroma_model=_DEPENDENCIES["model"],
            chroma_collection=_DEPENDENCIES["collection"],
            openai_client=_DEPENDENCIES["openai"],
            vector_db_path=VECTOR_DB_PATH,
        )
        
        response = await pipeline.ask(request)
        return response
    
    finally:
        # Always close connection after request to save Railway resources
        db_conn.close()

# ── Static Files ──
frontend_dir = os.path.join(os.getcwd(), "Frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)