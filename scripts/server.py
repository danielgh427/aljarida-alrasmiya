#!/usr/bin/env python3
"""
Startup script — Lebanese Laws & Tenders RAG System
Re-exported from scripts/ for convenience (invoked by start_server.bat).

Run directly:  python scripts/server.py
"""
import sys
import os
import uvicorn

# Resolve imports when executed from scripts/ or project root
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.main import app   # noqa: E402


if __name__ == "__main__":
    print("=" * 60)
    print("Lebanese Laws & Tenders RAG System")
    print("=" * 60)
    print("Starting API server...")
    print("API Documentation : http://localhost:8000/docs")
    print("Health Check       : http://localhost:8000/health")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
