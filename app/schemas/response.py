"""Response DTO — RAG chatbot endpoint."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SourceLaw(BaseModel):
    rank: int
    source_type: str = "law"
    law_title: str
    law_number: Optional[str] = None
    law_type: Optional[str] = None
    law_date: Optional[str] = None
    law_content: Optional[str] = None
    excerpt: Optional[str] = None
    percentage: Optional[float] = None
    link: Optional[str] = None


class SourceTender(BaseModel):
    rank: int
    source_type: str = "tender"
    tender_title: str
    description: Optional[str] = None
    location: Optional[str] = None
    deadline: Optional[str] = None
    excerpt: Optional[str] = None
    percentage: Optional[float] = None
    link: Optional[str] = None


class AskResponse(BaseModel):
    """Union response returned by POST /ask."""
    answer: str
    sources: List[Dict[str, Any]]
    detected_category: str
