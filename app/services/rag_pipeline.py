"""RAG pipeline — orchestrates embedding model, vector DB, MySQL, and LLM."""
from __future__ import annotations

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


def _fetch_latest_laws(cursor: Any) -> tuple[str, List[Dict[str, Any]]]:
    """Return (context, sources) for the 5 most-recent laws."""
    cursor.execute("SELECT * FROM laws ORDER BY scraped_at DESC LIMIT 5")
    rows = cursor.fetchall()

    rows.sort(
        key=lambda x: parse_law_date(x.get("law_date")),
        reverse=True,
    )
    rows = rows[:5]

    sources: List[Dict[str, Any]] = []
    context_parts: List[str] = []

    for i, row in enumerate(rows):
        meta = {
            "source_type": "law",
            "title": row.get("title", ""),
            "law_number": row.get("law_number", ""),
            "law_type": row.get("law_type", ""),
            "law_date": row.get("law_date", ""),
            "link": row.get("link", ""),
        }
        content = row.get("content", "") or ""
        sources.append(_build_source(i + 1, meta, content, 100 - (i * 5)))
        context_parts.append(
            f"SOURCE {i+1}\n"
            f"رقم القانون: {meta['law_number']}\n"
            f"عنوان القانون: {meta['title']}\n"
            f"نوع القانون: {meta['law_type']}\n"
            f"تاريخ القانون: {meta['law_date']}\n\n"
            f"{content}"
        )

    return "\n".join(context_parts), sources


_EXACT_SEARCH_PROMPT_TEMPLATE = """أنت مساعد قانوني متخصص تابع لنظام البحث عن القوانين واللوائح.

تم العثور على القانون المطلوب بنجاح. إليك المعلومات الكاملة:

{context}

تعليمات صريحة:
1. يجب عليك الإجابة على أساس المصادر أعلاه فقط
2. المعلومات موجودة بالفعل في المصادر أعلاه
3. لا تقل "لا توجد معلومات" - المعلومات موجودة هنا
4. قدم إجابة شاملة تتضمن: العنوان، الرقم، النوع، التاريخ، والملخص

السؤال: {question}

الإجابة:"""


def _build_source(
    rank: int,
    meta: Dict[str, Any],
    content: str,
    percentage: float,
) -> Dict[str, Any]:
    """Transform raw ChromaDB metadata + content into a structured source dict."""
    source_type = meta.get("source_type", "law")
    if source_type == "tender" or meta.get("summary") or meta.get("document_location"):
        title = meta.get("title", "")
        location = meta.get("document_location", "")
        if location == title:
            location = ""
        return {
            "rank": rank,
            "source_type": "tender",
            "tender_title": title,
            "description": meta.get("summary", ""),
            "location": location,
            "deadline": meta.get("final_submission_deadline", ""),
            "excerpt": content,
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
        "law_content": content,
        "excerpt": content,
        "percentage": round(percentage, 1),
        "link": meta.get("link", ""),
    }


def _safe_ai_answer(
    openai_client: OpenAI, prompt: str, sources: List[Dict[str, Any]]
) -> str:
    """Call OpenRouter LLM; fall back to top source excerpt on failure."""
    try:
        ai = openai_client.chat.completions.create(
            model="openai/gpt-oss-20b:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return ai.choices[0].message.content or ""

    except Exception:
        return sources[0].get("excerpt", "لا توجد نتائج.") if sources else "لا توجد نتائج."


_NO_INFO_PHRASES = [
    "لا تتوفر",
    "لا تتوفر في المصادر",
    "غير مذكور في المصادر",
    "لا أجد",
    "لا تحتوي المصادر",
    "لا توجد معلومات",
    "عذراً",
    "لم أتمكن",
    "لا تتوفر لديّ",
]


class RagPipeline:
    """Stateless orchestrator — instantiated once at process start-up.

    Static-side dependencies are injected so the same class can be reused
    in tests by passing mocks.
    """

    # Mapping: stream-cursor → request shape
    # Stored on the instance only; declared here for documentation purposes
    mysql_cursor: mysql.connector.cursor.MySQLCursor
    chroma_model: Any  # SentenceTransformer
    chroma_collection: chromadb.collections.Collection
    openai_client   : OpenAI
    vector_db_path  : str

    def __init__(
        self,
        *,
        mysql_cursor: Any,
        chroma_model: Any,
        chroma_collection: chromadb.collections.Collection,
        openai_client: OpenAI,
        vector_db_path: str,
    ) -> None:
        self.mysql_cursor     = mysql_cursor
        self.chroma_model     = chroma_model
        self.chroma_collection = chroma_collection
        self.openai_client    = openai_client
        self.vector_db_path   = vector_db_path

    # ── Public API ──────────────────────────────────────────────────

    async def ask(self, request: QuestionRequest) -> Dict[str, Any]:
        """Run the full RAG pipeline and return the structured response."""
        question = request.question.strip()

        try:
            return self._route(question, request)
        except Exception as exc:
            return {
                "answer": str(exc),
                "sources": [],
                "detected_category": request.category or "law",
            }

    # ── Internal routing ─────────────────────────────────────────────

    def _route(self, question: str, request: QuestionRequest) -> Dict[str, Any]:
        law_number  = extract_number(question)
        is_new_exact  = law_number is not None
        is_new_latest = is_latest_question(question)
        is_genuine_fu  = is_followup_question(question)

        should_reuse = (
            request.chat_history
            and request.previous_sources
            and not is_new_exact
            and not is_new_latest
            and is_genuine_fu
        )

        # ── Multi-turn follow-up ──────────────────────────────────────
        if should_reuse:
            prompt = build_prompt(question, request.previous_sources, request.chat_history)  # type: ignore[arg-type]
            answer = _safe_ai_answer(self.openai_client, prompt, request.previous_sources)
            return {
                "answer": answer,
                "sources": request.previous_sources if request.include_sources else [],
                "detected_category": (
                    request.previous_sources[0]["source_type"]
                    if request.previous_sources
                    else request.category or "law"
                ),
            }

        # ── Exact-number search ───────────────────────────────────────
        if is_new_exact:
            return self._exact_search(question, request)

        # ── "Latest" search ───────────────────────────────────────────
        if is_new_latest:
            return self._latest_search(question, request)

        # ── Hybrid search ─────────────────────────────────────────────
        return self._hybrid_search(question, request)

    # ── Search strategies ───────────────────────────────────────────

    def _exact_search(
        self, question: str, request: QuestionRequest
    ) -> Dict[str, Any]:
        patterns = [f"%{law_number}%" for law_number in [extract_number(question) or ""]]
        if request.chat_history:
            # Build patterns
            num = extract_number(question) or ""
            patterns = [f"%{num}%", num, f"% {num}%", f"%{num} %"]

        for pattern in [p for p in patterns if p]:
            if is_decree_question(question):
                self.mysql_cursor.execute(
                    """
                    SELECT * FROM laws
                    WHERE (law_number LIKE %s OR title LIKE %s)
                      AND law_type LIKE '%%مرسوم%%'
                    LIMIT 5
                    """,
                    (pattern, pattern),
                )
            else:
                self.mysql_cursor.execute(
                    """
                    SELECT * FROM laws
                    WHERE law_number LIKE %s OR title LIKE %s
                    LIMIT 5
                    """,
                    (pattern, pattern),
                )
            exact_rows = self.mysql_cursor.fetchall()
            if exact_rows:
                break
        else:
            # No results for any pattern
            return {
                "answer": (
                    "عذراً، لم أتمكن من العثور على قانون بهذا الرقم في قاعدة البيانات. "
                    "يرجى التحقق من رقم القانون أو السؤال عن موضوع آخر."
                ),
                "sources": [],
                "detected_category": "law",
            }

        sources: List[Dict[str, Any]] = []
        context_parts: List[str] = []

        for i, row in enumerate(exact_rows):
            meta = {
                "source_type": "law",
                "title":      row.get("title", ""),
                "law_number": row.get("law_number", ""),
                "law_type":   row.get("law_type", ""),
                "law_date":   row.get("law_date", ""),
                "link":       row.get("link", ""),
            }
            content = row.get("content", "") or ""
            if not content.strip():
                content = f"[تفاصيل غير محفوظة] - {meta['title']}"

            sources.append(_build_source(i + 1, meta, content, 100))
            context_parts.append(
                f"\n{'='*50}\n"
                f"SOURCE {i+1}: {meta['law_type']} رقم {meta['law_number']}\n"
                f"العنوان: {meta['title']}\n"
                f"التاريخ: {meta['law_date']}\n"
                f"{'='*50}\n{content}\n"
            )

        context = "\n".join(context_parts)
        prompt = _EXACT_SEARCH_PROMPT_TEMPLATE.format(context=context, question=question)
        answer = _safe_ai_answer(self.openai_client, prompt, sources)

        return {
            "answer": answer,
            "sources": sources,
            "detected_category": sources[0].get("source_type", "law") if sources else "law",
        }

    def _latest_search(
        self, question: str, request: QuestionRequest
    ) -> Dict[str, Any]:
        context, sources = _fetch_latest_laws(self.mysql_cursor)

        prompt = (
            "أجب فقط حسب المصادر التالية:\n\n"
            f"{context}\n\n"
            f"السؤال:\n{question}"
        )
        answer = _safe_ai_answer(self.openai_client, prompt, sources)

        return {
            "answer": answer,
            "sources": sources,
            "detected_category": sources[0].get("source_type", "law") if sources else "law",
        }

    def _hybrid_search(
        self, question: str, request: QuestionRequest
    ) -> Dict[str, Any]:
        query_text = question.strip()
        query_vec  = self.chroma_model.encode("query: " + query_text).tolist()

        where_filter: Optional[Dict[str, str]] = (
            {"source_type": request.category}
            if request.category in ("law", "tender")
            else None
        )

        semantic_results = self.chroma_collection.query(
            query_embeddings=[query_vec],
            n_results=request.max_results,
            where=where_filter,
        )

        candidates: List[Dict[str, Any]] = []
        seen_keys: set = set()

        docs      = semantic_results.get("documents", [[]])[0]
        metas     = semantic_results.get("metadatas",  [[]])[0]
        distances = semantic_results.get("distances", [[]])[0]

        for i in range(len(docs)):
            content = docs[i]
            meta    = metas[i]
            dist    = distances[i]

            sem_score   = max(0.0, 1.0 - (dist / 1.5))
            date_score  = extract_date_score(meta.get("law_date", ""))
            kw_score    = keyword_bonus(query_text, content)
            final_score = sem_score * 0.55 + date_score * 0.25 + kw_score * 0.20

            source_key = (content[:180], meta.get("link", ""), meta.get("law_number", ""))
            if source_key in seen_keys:
                continue
            seen_keys.add(source_key)

            candidates.append({"content": content, "meta": meta, "score": final_score})

        # ── MySQL lexical fallback ───────────────────────────────────
        if request.category in ("all", "law"):
            self.mysql_cursor.execute(
                """
                SELECT * FROM laws
                WHERE title LIKE %s OR content LIKE %s OR law_number LIKE %s
                LIMIT 5
                """,
                (f"%{query_text}%", f"%{query_text}%", f"%{query_text}%"),
            )
            exact_rows = self.mysql_cursor.fetchall()

            for row in exact_rows:
                content = row.get("content", "") or ""
                meta = {
                    "source_type": "law",
                    "title":      row.get("title", ""),
                    "law_number": row.get("law_number", ""),
                    "law_type":   row.get("law_type", ""),
                    "law_date":   row.get("law_date", ""),
                    "link":       row.get("link", ""),
                }
                source_key = (content[:180], meta.get("link", ""), meta.get("law_number", ""))
                if source_key in seen_keys:
                    continue
                seen_keys.add(source_key)

                date_score = extract_date_score(meta.get("law_date", ""))
                kw_score   = keyword_bonus(query_text, content)
                lex_score  = 0.45 + date_score * 0.25 + kw_score * 0.30

                candidates.append({"content": content, "meta": meta, "score": lex_score})

        # ── Rank & select ────────────────────────────────────────────
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top = candidates[: request.max_results]

        if not top:
            return {
                "answer": (
                    "عذراً، لم أتمكن من العثور على معلومات عن سؤالك في قاعدة البيانات. "
                    "يرجى محاولة سؤال مختلف أو موضوع آخر."
                ),
                "sources": [],
                "detected_category": request.category or "law",
            }

        if is_vague_question(question):
            return {
                "answer": (
                    "عذراً، سؤالك غير واضح. يرجى تقديم سؤال أكثر تحديداً مثل:\n"
                    "- 'ما هي قوانين الاستثمار؟'\n"
                    "- 'أخبرني عن القانون رقم 620'\n"
                    "- 'ما هي آخر المراسيم؟'"
                ),
                "sources": [],
                "detected_category": request.category or "law",
            }

        sources = [
            _build_source(i + 1, item["meta"], item["content"], item["score"] * 100)
            for i, item in enumerate(top)
        ]

        if not check_confidence_threshold(sources):
            return {
                "answer": (
                    "عذراً، لم أتمكن من العثور على معلومات دقيقة كافية عن سؤالك. يرجى:\n"
                    "- إعادة صياغة السؤال بشكل أكثر وضوحاً\n"
                    "- تقديم كلمات مفتاحية أكثر تحديداً\n"
                    "- السؤال عن موضوع أو قانون معين"
                ),
                "sources": [],
                "detected_category": request.category or "law",
            }

        prompt = build_prompt(question, sources, request.chat_history)
        answer = _safe_ai_answer(self.openai_client, prompt, sources)

        # Detect LLM "no knowledge" response
        answer_lower = answer.lower()
        is_no_info = any(phrase in answer_lower for phrase in _NO_INFO_PHRASES)

        if is_no_info:
            return {
                "answer": answer,
                "sources": [],
                "detected_category": (sources[0].get("source_type", request.category or "law") if sources else request.category or "law"),
            }

        return {
            "answer": answer,
            "sources": sources if request.include_sources else [],
            "detected_category": (sources[0].get("source_type", request.category or "law") if sources else request.category or "law"),
        }
