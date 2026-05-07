# Lebanese Laws & Tenders RAG Chatbot

## Project Overview

This project is an AI-powered Retrieval-Augmented Generation (RAG) chatbot designed to answer questions related to Lebanese laws and government tenders.

The system combines:

* MySQL structured data storage
* Chroma vector database
* multilingual semantic embeddings
* FastAPI backend
* LLM response generation

The chatbot retrieves relevant legal and tender information semantically before generating answers.

---

# Main Features

* Semantic search over Lebanese laws
* Semantic search over public tenders
* Tender-law matching capability
* Multilingual embedding support
* FastAPI REST API backend
* Vector similarity retrieval using ChromaDB

---

# System Architecture

```text
User Question
     ↓
FastAPI Backend
     ↓
Embedding Generation (query embedding)
     ↓
Vector Search in ChromaDB
     ↓
Retrieve Relevant Laws / Tenders
     ↓
LLM Response Generation
     ↓
Answer Returned to User
```

---

# Project Structure

```text
project/
│
├── api/
│   └── rag_chatbot.py
│
├── embeddings/
│   ├── generate_embeddings.py
│   ├── fetch_laws.py
│   ├── fetch_tenders.py
│   └── vector_store.py
│
├── data/
│   └── vector_db/
│
├── Frontend/
│   ├──chatbot.js
│   ├──index.html
│   └──styles.css
│
├──database/
│  ├──create_tables.sql
│  └──db_connection.py
│
├── config.py
├── run_server.py
├── requirements.txt
└── README.md
```

---

# Core Components

---

# 1 FastAPI Backend

Main API file:

```text
api/rag_chatbot.py
```

Responsible for:

* receiving user questions
* calling semantic retrieval
* generating final response

Main endpoint:

```text
POST /ask
```

---

# 2 Embedding Generation

Main file:

```text
embeddings/generate_embeddings.py
```

Uses model:

```text
intfloat/multilingual-e5-base
```

Generates embeddings for:

* laws
* tenders

Stored metadata includes:

## Laws

* title
* law number
* law type
* law date
* content
* link

## Tenders

* title
* summary
* location
* deadline
* link

---

# 3 Database Retrieval

## Laws source

```text
fetch_laws.py
```

Reads legal documents from MySQL.

## Tenders source

```text
fetch_tenders.py
```

Reads tenders from MySQL.

---

# 4 Vector Database

Main storage:

```text
data/vector_db/
```

Uses:

```text
ChromaDB
```

Stores:

* embeddings
* ids
* metadata
* documents

---

---

# 5 Vector Store Initialization

Main file:

```text
vector_store.py
```

This file:

* generates embeddings
* stores vectors inside ChromaDB

Run before starting chatbot:

```bash
python embeddings/vector_store.py
```

---

# 6 Configuration

Main file:

```text
config.py
```

Contains:

```python
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "ai_tender_laws"
```

Also:

```python
VECTOR_DB_PATH
```

for vector database path.

---

# 7 Server Startup

Main file:

```text
run_server.py
```

Run:

```bash
python run_server.py
```

or:

```bash
uvicorn api.rag_chatbot:app --reload
```

---

# Installation

---

# Step 1 Create virtual environment

```bash
python -m venv venv
```

---

# Step 2 Activate virtual environment

Windows:

```bash
venv\Scripts\activate
```

---

# Step 3 Install dependencies

```bash
pip install -r requirements.txt
```

---

# requirements.txt

```txt
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
chromadb>=0.4.18
sentence-transformers>=2.2.2
openai>=1.3.7
mysql-connector-python>=8.2.0
torch>=2.1.1
numpy>=1.24.0
requests>=2.31.0
Pillow>=10.1.0
python-dotenv>=1.0.0
beautifulsoup4>=4.12.2
```

---

# Execution Order

Always run in this order:

```text
1 Start MySQL
2 Install requirements
3 Generate embeddings
4 Start backend server
5 Open frontend
```

---

# Generate Embeddings First

```bash
python embeddings/vector_store.py
```

Required because:

Without embeddings, retrieval will return empty results.

---

# Start Backend

```bash
python run_server.py
```

API docs:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/health
```

---

# Database Requirements

MySQL database must contain:

## laws table

## tenders table

Required before embeddings generation.

---

# If Sharing Project with Another Person

Send:

* project folder
* database export (.sql)
* README.md
* requirements.txt

Then they run:

```bash
pip install -r requirements.txt
python embeddings/vector_store.py
python run_server.py
```

---

# Important Development Note

If tenders are updated:

regenerate embeddings again:

```bash
python embeddings/vector_store.py
```

This ensures ChromaDB stays synchronized.

---

# Academic Purpose

This system is developed as part of a graduation project for:

AI chatbot for Lebanese laws and government tender matching.
