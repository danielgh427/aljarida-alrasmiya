"""RAG pipeline — orchestrates embedding model, vector DB, MySQL, and LLM."""
from __future__ import annotations

import re
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import chromadb
import mysql.connector
from openai import OpenAI

from app.schemas.request import QuestionRequest
from app.services.helpers import (
    build_prompt,
    check_confidence_threshold,
    extract_date_score,
    extract_number,
    is_decree_question,
    is_followup_question,
    is_latest_question,
    is_vague_question,
    keyword_bonus,
    parse_law_date,
)

logger = logging.getLogger("AlJarida-Pipeline")

# ── Helper: Fetch Latest Laws with Proper Parsing ───────────────────

def _fetch_latest_laws(cursor: Any) -> tuple[str, List[Dict[str, Any]]]:
    """Return (context, sources) for the 5 most-recent laws by parsing the date string."""
    cursor.execute("SELECT * FROM laws")
    rows = cursor.fetchall()

    def clean_and_parse(date_str):
        if not date_str:
            return datetime.min
        # Fix: Remove Arabic prefix "تاريخ " and extra spaces to get "DD/MM/YYYY"
        clean_str = date_str.replace("تاريخ", "").strip()
        return parse_law_date(clean_str)

    # Sort by parsed date (newest first), then by ID as tie-breaker
    rows.sort(
        key=lambda row: (clean_and_parse(row.get("law_date")), row.get("id", 0)),
        reverse=True,
    )
    
    top_rows = rows[:5]
    sources: List[Dict[str, Any]] = []
    context_parts: List[str] = []

    for i, row in enumerate(top_rows):
        meta = {
            "source_type": "law",
            "title": row.get("title", ""),
            "law_number": row.get("law_number", ""),
            "law_type": row.get("law_type", ""),
            "law_date": row.get("law_date", ""),
            "link": row.get("link", ""),
        }
        content = row.get("content", "") or ""
        sources.append(_build_source(i + 1, meta, content, 100 - i))
        context_parts.append(
            f"SOURCE {i+1}\n"
            f"العنوان: {meta['title']}\n"
            f"التاريخ: {meta['law_date']}\n"
            f"المحتوى: {content}\n"
        )

    return "\n".join(context_parts), sources


# ── Helper: Formatting Sources for Frontend ──────────────────────────

def _build_source(rank: int, meta: Dict[str, Any], content: str, percentage: float) -> Dict[str, Any]:
    """Transform raw metadata + content into a structured source dict."""
    source_type = meta.get("source_type", "law")
    
    if source_type == "tender" or meta.get("summary") or meta.get("document_location"):
        return {
            "rank": rank,
            "source_type": "tender",
            "tender_title": meta.get("title", ""),
            "description": meta.get("summary", ""),
            "location": meta.get("document_location", ""),
            "deadline": meta.get("final_submission_deadline", ""),
            "excerpt": content[:800], # Send chunk to frontend
            "percentage": round(percentage, 1),
            "link": meta.get("link", ""),
        }

    return {
        "rank": rank,
        "source_type": "law",
        "law_title": meta.get("title", ""),
        "law_number": meta.get("law_number", ""),
        "law_type": meta.get("law_type", ""),
        "law_date": meta.get("law_date", ""),
        "excerpt": content[:800],
        "percentage": round(percentage, 1),
        "link": meta.get("link", ""),
    }


# ── Main Pipeline Class ──────────────────────────────────────────────

class RagPipeline:
    def __init__(
        self,
        *,
        mysql_cursor: Any,
        chroma_model: Any,
        chroma_collection: chromadb.collections.Collection,
        openai_client: OpenAI,
        vector_db_path: str,
    ) -> None:
        self.mysql_cursor = mysql_cursor
        self.chroma_model = chroma_model
        self.chroma_collection = chroma_collection
        self.openai_client = openai_client

    async def ask(self, request: QuestionRequest) -> Dict[str, Any]:
        """Entry point for the question-answering logic."""
        question = request.question.strip()
        
        # Decide search strategy
        law_number = extract_number(question)
        is_latest = is_latest_question(question)
        is_followup = is_followup_question(question)

        # 1. Multi-turn Follow-up Logic
        # If user says "tell me more" and we have previous results, don't search again
        if is_followup and request.previous_sources and not law_number and not is_latest:
            logger.info("Routing: Multi-turn Follow-up")
            sources = request.previous_sources
            context = "\n".join([f"Source {s['rank']}: {s.get('excerpt','')}" for s in sources])
        
        # 2. Exact Law Number Search
        elif law_number:
            logger.info(f"Routing: Exact Search for {law_number}")
            return self._exact_search(question, law_number)

        # 3. Chronological "Latest" Search
        elif is_latest:
            logger.info("Routing: Latest Laws Search")
            context, sources = _fetch_latest_laws(self.mysql_cursor)

        # 4. Semantic / Hybrid Search (Default)
        else:
            logger.info("Routing: Hybrid Semantic Search")
            return self._hybrid_search(question, request)

        # Generate Final AI Answer
        prompt = self._build_final_prompt(question, context, request.chat_history)
        answer = self._call_llm(prompt, sources)

        return {
            "answer": answer,
            "sources": sources,
            "detected_category": sources[0]["source_type"] if sources else "law"
        }

    # ── Search Strategies ──

    def _exact_search(self, question: str, num: str) -> Dict[str, Any]:
        # Search by number in MySQL
        query = "SELECT * FROM laws WHERE law_number LIKE %s OR title LIKE %s LIMIT 3"
        self.mysql_cursor.execute(query, (f"%{num}%", f"%{num}%"))
        rows = self.mysql_cursor.fetchall()

        if not rows:
            return {"answer": f"عذراً، لم أجد قانوناً بالرقم {num} في سجلاتي.", "sources": []}

        sources = []
        context = ""
        for i, row in enumerate(rows):
            sources.append(_build_source(i+1, row, row['content'], 100))
            context += f"قانون رقم {row['law_number']}: {row['title']}\nالمحتوى: {row['content']}\n"

        prompt = f"استخدم النص التالي للإجابة بدقة عن القانون رقم {num}:\n{context}\nالسؤال: {question}"
        answer = self._call_llm(prompt, sources)
        return {"answer": answer, "sources": sources, "detected_category": "law"}

    def _hybrid_search(self, question: str, request: QuestionRequest) -> Dict[str, Any]:
        # Semantic query in ChromaDB
        query_vec = self.chroma_model.encode("query: " + question).tolist()
        
        # Apply category filter if selected in UI
        where_filter = {"source_type": request.category} if request.category in ["law", "tender"] else None
        
        results = self.chroma_collection.query(
            query_embeddings=[query_vec], 
            n_results=request.max_results,
            where=where_filter
        )

        sources = []
        context = ""
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for i in range(len(docs)):
            score = max(0, 100 - (dists[i] * 50))
            sources.append(_build_source(i+1, metas[i], docs[i], score))
            context += f"المصدر {i+1}: {docs[i]}\n"

        if not sources:
            return {"answer": "لم أجد نتائج مطابقة لبحثك. حاول تغيير كلمات البحث.", "sources": []}

        prompt = self._build_final_prompt(question, context, request.chat_history)
        answer = self._call_llm(prompt, sources)
        return {"answer": answer, "sources": sources, "detected_category": sources[0]["source_type"]}

    # ── LLM Utilities ──

    def _build_final_prompt(self, question: str, context: str, history: List[Any]) -> str:
        history_str = "\n".join([f"{m.role}: {m.content}" for m in history[-4:]])
        return f"""
أنت مساعد خبير في القوانين والمناقصات اللبنانية. 
أجب بناءً على المصادر المقدمة فقط. تجاهل المقدمات الروتينية مثل "بناءً على الدستور" إلا إذا كانت هي صلب السؤال.

سياق المحادثة السابقة:
{history_str}

المصادر القانونية:
{context}

السؤال الحالي: {question}
الإجابة المفصلة باللغة العربية:"""

    def _call_llm(self, prompt: str, sources: List[Dict[str, Any]]) -> str:
        try:
            response = self.openai_client.chat.completions.create(
                model="openai/gpt-3.5-turbo", # Recommended for speed/cost on Railway
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1 # Low temperature for factual accuracy
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return sources[0].get("excerpt", "عذراً، تعذر الوصول للذكاء الاصطناعي حالياً.") if sources else "عذراً، حدث خطأ."