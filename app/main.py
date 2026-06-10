import sys
import os
import logging
from dotenv import load_dotenv

# 1. Load env before everything else
load_dotenv()

# Disable symlinks for HuggingFace to avoid Railway filesystem errors
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import uvicorn
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Setup logging to see errors in Railway Dashboard
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import VECTOR_DB_PATH
from app.schemas.request import QuestionRequest
from app.services.rag_pipeline import RagPipeline
from app.database.db_connection import connect_db

app = FastAPI(title="Lebanese Law & Tenders Robust RAG")

app.add_middleware(
   CORSMiddleware,
   allow_origins=["*"], 
   allow_credentials=True,
   allow_methods=["*"],  
   allow_headers=["*"],
)

# ── Dependencies Initialized once ──
# We wrap this in a try-block for Railway DB stability
try:
    _db_conn = connect_db()
    _DB_CURSOR = _db_conn.cursor(dictionary=True)
    logger.info("✅ MySQL Connected")
except Exception as e:
    logger.error(f"❌ MySQL Connection Failed: {e}")
    _DB_CURSOR = None

# Load model (Note: Railway might take 60s to start because of this line)
logger.info("⏳ Loading Embedding Model...")
_model = SentenceTransformer("intfloat/multilingual-e5-small")
logger.info("✅ Model Loaded")

_chroma_cli = chromadb.PersistentClient(path=VECTOR_DB_PATH)
_collection = _chroma_cli.get_or_create_collection("rag_collection")

_openai = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

# Initialize Pipeline
pipeline = RagPipeline(
    mysql_cursor=_DB_CURSOR,
    chroma_model=_model,
    chroma_collection=_collection,
    openai_client=_openai,
    vector_db_path=VECTOR_DB_PATH,
)

# ── Routes ──
@app.get("/health")
def health():
    return {"status": "ok", "db": "connected" if _DB_CURSOR else "disconnected"}

@app.post("/ask")
async def ask(request: QuestionRequest):
    # Ensure DB cursor is still alive or handle it inside pipeline
    return await pipeline.ask(request)

# ── Static Files ──
# Logic: If running on Railway, serve the 'Frontend' folder
frontend_dir = os.path.join(os.getcwd(), "Frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"✅ Serving Frontend from {frontend_dir}")
else:
    logger.warning("⚠️ Frontend directory not found!")

if __name__ == "__main__":
    # Railway uses 'PORT' environment variable
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)