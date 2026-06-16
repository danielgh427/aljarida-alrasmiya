"""RAG pipeline — orchestrates embedding model, vector DB, MySQL, and LLM."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import chromadb
from openai import OpenAI

from app.schemas.request import QuestionRequest
from app.services.helpers import (
    extract_date_score,
    extract_number,
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
        clean_str = str(date_str).replace("تاريخ", "").strip()
        return parse_law_date(clean_str)

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
            "excerpt": content[:800],
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

        if is_vague_question(question):
            return {
                "answer": "عذراً، سؤالك غير واضح بما يكفي. هل يمكنك تحديد موضوع معين؟",
                "sources": [],
                "detected_category": request.category or "law"
            }
        
        law_number = extract_number(question)
        is_latest = is_latest_question(question)
        is_followup = is_followup_question(question)

        sources = []
        context = ""

        if law_number:
            return self._exact_search(question, law_number)

        elif is_latest:
            context, sources = _fetch_latest_laws(self.mysql_cursor)

        elif is_followup and request.previous_sources:
            sources = request.previous_sources
            context = "\n".join([f"المصدر: {s.get('law_title', s.get('tender_title', ''))}\nالنص: {s.get('excerpt','')}" for s in sources])
        
        else:
            return self._hybrid_search(question, request)

        prompt = self._build_final_prompt(question, context, request.chat_history)
        answer = self._call_llm(prompt, sources)

        return {
            "answer": answer,
            "sources": sources,
            "detected_category": sources[0].get("source_type", "law") if sources else "law"
        }

    def _exact_search(self, question: str, num: str) -> Dict[str, Any]:
        query = "SELECT * FROM laws WHERE law_number LIKE %s OR title LIKE %s LIMIT 3"
        self.mysql_cursor.execute(query, (f"%{num}%", f"%{num}%"))
        rows = self.mysql_cursor.fetchall()

        if not rows:
            return {"answer": f"عذراً، لم أجد قانوناً بالرقم {num}.", "sources": []}

        sources = []
        context = ""
        for i, row in enumerate(rows):
            sources.append(_build_source(i+1, row, row.get('content', ''), 100))
            context += f"قانون رقم {row.get('law_number')}: {row.get('title')}\nالمحتوى: {row.get('content')}\n"

        prompt = f"استخدم النص التالي للإجابة بدقة عن القانون رقم {num}:\n{context}\nالسؤال: {question}"
        answer = self._call_llm(prompt, sources)
        return {"answer": answer, "sources": sources, "detected_category": "law"}

    def _hybrid_search(self, question: str, request: QuestionRequest) -> Dict[str, Any]:
        query_vec = self.chroma_model.encode("query: " + question).tolist()
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
            final_pct = self._compute_hybrid_score(
                distance=dists[i],
                metadata=metas[i],
                question=question,
                content=docs[i],
            )
            sources.append(_build_source(i + 1, metas[i], docs[i], final_pct))
            context += f"المصدر {i + 1}: {docs[i]}\n"

        if not sources or sources[0]['percentage'] < 35:
            return {"answer": "عذراً، لم أجد نتائج مطابقة تماماً لسؤالك.", "sources": []}

        prompt = self._build_final_prompt(question, context, request.chat_history)
        answer = self._call_llm(prompt, sources)
        return {"answer": answer, "sources": sources, "detected_category": sources[0].get("source_type", "law")}

    def _compute_hybrid_score(
        self,
        distance: float,
        metadata: Dict[str, Any],
        question: str,
        content: str,
    ) -> float:
        """Rank results with semantic, date recency, and keyword overlap."""
        sem_score = max(0.0, 100.0 - (distance * 50.0))
        date_score = extract_date_score(metadata.get("law_date") or metadata.get("date")) * 100.0
        keyword_bonus_val = keyword_bonus(question, content) * 100.0
        return round(
            (sem_score * 0.55) + (date_score * 0.25) + (keyword_bonus_val * 0.20), 1
        )

    def _build_final_prompt(self, question: str, context: str, history: List[Dict[str, Any]]) -> str:
        history_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-4:]])
        return f"سياق المحادثة:\n{history_str}\n\nالمصادر:\n{context}\n\nالسؤال: {question}\nالإجابة بالعربية:"

    def _call_llm(self, prompt: str, sources: List[Dict[str, Any]]) -> str:
        try:
            response = self.openai_client.chat.completions.create(
                model="openai/gpt-oss-20b:free",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1 
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return sources[0].get("excerpt", "عذراً، تعذر الوصول للذكاء الاصطناعي.") if sources else "خطأ."