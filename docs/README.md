# Lebanese Laws & Tenders RAG Chatbot

## Project Overview

This project is an AI-powered Retrieval-Augmented Generation (RAG) chatbot designed to answer questions related to Lebanese laws and government tenders written in both arabic and english.

The system combines:

- MySQL structured data storage
- Chroma vector database
- Multilingual semantic embeddings
- FastAPI backend
- LLM response generation via OpenRouter

The chatbot retrieves relevant legal and tender information semantically before generating answers.

## Live Demo

- Production: [Al Jarida AI - تفاعل ذكي مع القوانين والمناقصات](https://aljarida-alrasmiya-production-bf58.up.railway.app/)
- Local API: `http://localhost:8000`

---

## Main Features

- Semantic search over Lebanese laws
- Semantic search over public tenders
- Tender-law matching capability
- Multilingual embedding support (`intfloat/multilingual-e5-base`)
- FastAPI REST API backend
- Vector similarity retrieval using ChromaDB
- Bilingual support (Arabic & English) via frontend

---

## System Architecture

```text
User Question
     ↓
FastAPI Backend  (app/main.py)
     ↓
Embedding Generation — query embedding  (app/services/rag_pipeline.py)
     ↓
Vector Search in ChromaDB  (data/vector_db/)
     ↓
Retrieve Relevant Laws / Tenders from MySQL  (app/database/db_connection.py)
     ↓
LLM Response Generation via OpenRouter
     ↓
Answer Returned to User  (app/schemas/response.py)
```

---

## Project Structure

```text
project/
├── app/
│   ├── main.py                      # FastAPI app & entry-point
│   ├── database/
│   │   ├── db_connection.py         # MySQL connection factory
│   │   └── schema.sql               # MySQL schema (laws + tenders tables)
│   ├── schemas/
│   │   ├── request.py               # Pydantic request DTO (QuestionRequest)
│   │   └── response.py              # Pydantic response DTO (AskResponse)
│   ├── services/
│   │   ├── helpers.py               # Pure utility functions (prompts, heuristics)
│   │   └── rag_pipeline.py          # Full RAG orchestration + confidence scoring
│   └── middleware/                  # (placeholder for future middleware)
│
├── services/
│   └── embeddings/
│       ├── rag_engine.py             # Embedding model wrapper & generation logic
│       ├── fetch_laws.py             # Reads laws from MySQL
│       ├── fetch_tenders.py          # Reads tenders from MySQL
│       └── vector_store.py           # ChromaDB index builder / rebuild entry-point
│
├── scraping/
│   ├── laws_workflow.json            # n8n workflow — scrape Lebanese laws
│   └── tenders_workflow.json         # n8n workflow — scrape Lebanese tenders
│
├── scripts/
│   ├── server.py                     # Startup wrapper — runs uvicorn + log banner
│   └── start_server.bat              # Windows launcher (double-click)
│
├── Frontend/
│   ├── index.html                    # Chat UI (Arabic-first, RTL)
│   ├── chatbot.js                    # Frontend logic — fetches /ask, shows sources
│   └── styles.css                    # Styling
│
├── docs/
│   ├── README.md                     # This file
│   └── architecture/                 # Stack & sequence diagrams (.mermaid files)
│       ├── diagram-01-system-context.mermaid
│       ├── diagram-02-layered-architecture.mermaid
│       ├── diagram-03-chat-sequence.mermaid
│       ├── diagram-04-embeddings-pipeline.mermaid
│       ├── diagram-05-deployment.mermaid
│       └── diagram-06-stack-map.mermaid
│
├── data/
│   └── vector_db/                    # ChromaDB persistence (gitignored)
│
├── config.py                         # DB credentials + VECTOR_DB_PATH
├── requirements.txt                  # Python dependencies
├── .env                              # Real secrets (local only — gitignored)
└── .env.example                      # Environment vars template
```

---

## Core Components

### 1. FastAPI Backend (`app/main.py`)

Single entry-point. Warm-starts all dependencies at import time:

- MySQL connection
- `SentenceTransformer` model (`intfloat/multilingual-e5-base`)
- ChromaDB persistent client
- OpenRouter-compatible `OpenAI` client

Exposes:

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Returns `{"status": "ok"}` |
| `/ask` | POST | Accepts `QuestionRequest`, returns `AskResponse` |

### 2. RAG Pipeline (`app/services/rag_pipeline.py`)

Orchestrates the full pipeline. Handles:

- Category detection (laws, tenders, both)
- Embedding of the user question
- Vector similarity search in ChromaDB
- MySQL row enrichment
- Confidence thresholding with keyword/latest-law bonuses
- Follow-up and vague-question detection
- LLM prompt construction via `helpers.py`

### 3. Request / Response DTOs

**`app/schemas/request.py`** — `QuestionRequest`:

```python
class QuestionRequest(BaseModel):
    question: str
    category: Optional[str] = "all"   # "law" | "tender" | "all"
    max_results: int = 8
    include_sources: bool = True
    chat_history: Optional[List[Dict]] = None
    previous_sources: Optional[List[Dict]] = None
```

**`app/schemas/response.py`** — `AskResponse`, `SourceLaw`, `SourceTender`:

```python
class AskResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    detected_category: str
```

### 4. Helpers (`app/services/helpers.py`)

Pure functions: `build_prompt`, `check_confidence_threshold`, `keyword_bonus`,
`is_decree_question`, `is_followup_question`, `is_latest_question`,
`is_vague_question`, `parse_law_date`, `extract_date_score`, `extract_number`.

### 5. Database (`app/database/`)

| File | Purpose |
|---|---|
| `db_connection.py` | `connect_db()` → MySQL connection factory |
| `schema.sql` | Creates `laws` and `tenders` tables |

MySQL tables:

- **`laws`** — id, link, title, law_type, law_number, law_date, content, scraped_at
- **`tenders`** — id, link, title, summary, final_submission_deadline,
  opening_session_date, document_price, document_location, created_at

### 6. Embedding Services (`services/embeddings/`)

Split into three modules so the heavy model can be ring-fenced.

| File | Purpose |
|---|---|
| `rag_engine.py` | `get_model()` lazy-loads `SentenceTransformer("intfloat/multilingual-e5-base")`; applies `"passage: "` prefix when encoding documents |
| `fetch_laws.py` | `get_laws()` — SELECTs all rows from the `laws` table |
| `fetch_tenders.py` | `get_tenders()` — SELECTs all rows from the `tenders` table |
| `vector_store.py` | `store_vectors()` — builds / rebuilds the ChromaDB index. Run: `python -m services.embeddings.vector_store` |

Model: `intfloat/multilingual-e5-base`  
Prefix mandated by the E5 family: `"passage: "` (documents), `"query: "` (questions — added automatically by the RAG pipeline).

### 7. n8n Scraping Workflows (`scraping/`)

| File | Purpose |
|---|---|
| `laws_workflow.json` | n8n graph: paginate legislation portal → HTTP request → HTML extract → JS transform → MySQL upsert |
| `tenders_workflow.json` | n8n graph: scrape tender listings → HTTP request → HTML extract → JS transform → MySQL upsert |

### 8. Configuration (`config.py`)

```python
DB_HOST     = "localhost"
DB_USER     = "root"
DB_PASSWORD = ""
DB_NAME     = "ai_tender_laws"

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "data", "vector_db")
```

A `.env` file may also be used for `OPENROUTER_API_KEY` (loaded by
`python-dotenv` in `app/main.py`). Use `.env.example` as your starting template.

### 9. Server Startup

Two ways to start:

```bash
# Option A — Windows batch file (double-click)
scripts\start_server.bat

# Option B — Direct Python
python scripts/server.py

# Option C — uvicorn directly (auto-reload on code changes)
uvicorn app.main:app --reload
```

Output URLs:

| URL | Purpose |
|---|---|
| `http://localhost:8000/docs` | Interactive Swagger / OpenAPI docs |
| `http://localhost:8000/health` | Health check |
| Frontend: `Frontend/index.html` | Local browser chat UI |

### 10. Frontend (`frontend/`)

Single-page app (Arabic-first, RTL).

- `index.html` — page skeleton, chat container, source panel
- `chatbot.js` — sends `POST /ask` with full `chat_history` and
  `previous_sources`; renders sidebar sources
- `styles.css` — layout and dark/light styling

---

## Installation

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate

```powershell
# PowerShell
.venv\Scripts\Activate.ps1

# CMD
.venv\Scripts\activate.bat
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Execution Order

Run every step in this order:

```text
1. Start MySQL
2. Install requirements        (pip install -r requirements.txt)
3. Import data into MySQL      (run n8n scraping workflows or manual import)
4. Generate/rebuild embeddings (python -m services.embeddings.vector_store)
5. Start backend server        (python scripts/server.py)
6. Open frontend               (frontend/index.html)
```

### 4. Populate MySQL

Scrape laws and tenders using n8n (import the workflow JSONs from the
`scraping/` folder into your n8n instance, then run them), or import the
`app/database/schema.sql` into MySQL and insert rows manually.

### 5. Generate Embeddings

```bash
python -m services.embeddings.vector_store
```

Embeddings must be generated *before* the chatbot runs — without them, retrieval
returns empty results.

### 6. Run the Server

```bash
python scripts/server.py
```

API is then available at `http://localhost:8000`.

### 7. Production Deployment

The public production deployment is available at:
- [Al Jarida AI - تفاعل ذكي مع القوانين والمناقصات](https://aljarida-alrasmiya-production-bf58.up.railway.app/)

For local development, use:
- API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Frontend UI: `Frontend/index.html`

Recommended production practice:
- Use a managed MySQL service.
- Keep `OPENROUTER_API_KEY` and database credentials in environment variables.
- Use Docker Compose for local development if desired:
  ```bash
  docker-compose up --build
  ```
- Rebuild the Chroma index after any data changes:
  ```bash
  python -m services.embeddings.vector_store
  ```

### 8. Security

This project includes Snyk scanning in GitHub Actions for:
- Python dependency vulnerabilities (`requirements.txt`)
- Docker container security checks (`Dockerfile`)

A sample Snyk workflow is defined in `.github/workflows/snyk.yml`.
- Docker image security (`Dockerfile`)

Security notes:
- Do not commit `data/vector_db/chroma.sqlite3`, `.env`, or `.venv`.
- Keep secret values in deployment environment variables only.
- Use `.env.example` as the template for local setup.

---

## Database Schema (`app/database/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS laws (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    link        VARCHAR(500) UNIQUE,
    title       TEXT,
    law_type    TEXT,
    law_number  VARCHAR(50),
    law_date    VARCHAR(50),
    content     LONGTEXT,
    scraped_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenders (
    id                        INT AUTO_INCREMENT PRIMARY KEY,
    link                      VARCHAR(500) UNIQUE,
    title                     TEXT,
    summary                   TEXT,
    final_submission_deadline DATETIME,
    opening_session_date      DATETIME,
    document_price            DECIMAL(15,2),
    document_location         TEXT,
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## `requirements.txt`

```txt
# Core dependencies
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
chromadb>=0.4.18
sentence-transformers>=2.2.2
openai>=1.3.7

# Database
mysql-connector-python>=8.2.0

# Embedding model
torch>=2.1.1

# Utilities
numpy>=1.24.0
requests>=2.31.0
Pillow>=10.1.0
python-dotenv>=1.0.0

# Optional scraping
beautifulsoup4>=4.12.2
```

---

## Rebuilding Embeddings

Any time the `laws` or `tenders` data changes run:

```bash
python -m services.embeddings.vector_store
```

This rebuilds the entire ChromaDB index and keeps Chroma in sync with MySQL.

---

## API Endpoints

### `GET /health`

Returns server status:

```json
{ "status": "ok" }
```

### `POST /ask`

```json
// Request
{
  "question": "ما هو القانون الجديد؟",
  "category": "all",
  "max_results": 8,
  "include_sources": true,
  "chat_history": null,
  "previous_sources": null
}
```

```json
// Response
{
  "answer": "الاجابة هنا",
  "sources": [
    {
      "rank": 1,
      "source_type": "law",
      "law_title": "...",
      "law_number": "...",
      "law_type": "...",
      "law_date": "...",
      "law_content": "...",
      "excerpt": "...",
      "percentage": 95.2,
      "link": "..."
    }
  ],
  "detected_category": "law"
}
```

---

## If Sharing This Project

Share:

1. The project folder (minus `.venv/`, `__pycache__/`, `.env`, `data/`)
2. A MySQL dump of the `ai_tender_laws` database
3. This README.md
4. `requirements.txt`

Recipient runs:

```bash
pip install -r requirements.txt
python -m services.embeddings.vector_store
python scripts/server.py
```

---

## Academic Purpose

This system is developed as part of a graduation project for:
**AI Chatbot for Lebanese Laws and Government Tender Matching.**
