"""Request DTO — RAG chatbot endpoint."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    category: Optional[str] = "all"
    max_results: int = 8
    include_sources: bool = True
    chat_history: Optional[List[Dict[str, Any]]] = None
    previous_sources: Optional[List[Dict[str, Any]]] = None
