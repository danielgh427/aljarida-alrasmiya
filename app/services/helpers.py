"""Pure helper utilities used by the RAG pipeline.

No I/O, no global mutable state — pure functions that can be unit-tested in
isolation without a running server or database connection.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Number / date helpers ────────────────────────────────────────────

def extract_number(question: str) -> Optional[str]:
    """Return the first digit cluster found in *question*, or ``None``."""
    match = re.search(r"(\d+)", question)
    return match.group(1) if match else None


def is_latest_question(question: str) -> bool:
    """``True`` when the question asks for the most-recent law / decree."""
    latest_words = ["آخر", "احدث", "أحدث", "الأخير", "latest", "newest", "recent"]
    return any(w in question.lower() for w in latest_words)


def is_decree_question(question: str) -> bool:
    """``True`` when the question is about a *مرسوم* (decree)."""
    return "مرسوم" in question


def parse_law_date(date_str: Optional[str]) -> datetime:
    """Parse a date string in any of the common Lebanese-law formats."""
    if not date_str:
        return datetime.min

    date_str = str(date_str).strip()

    formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return datetime.min


def extract_date_score(date_str: Optional[str]) -> float:
    """Return 0–1 the closer the date is to today (max = 1 for < 1yr old)."""
    dt = parse_law_date(date_str)
    if dt == datetime.min:
        return 0.0

    days = (datetime.now() - dt).days
    return max(0.0, 1.0 - (days / 3650.0))


# ── Classification guardrails ────────────────────────────────────────

_FOLLOWUP_PATTERNS: List[str] = [
    "أخبر", "أعطني", "هل هناك", "ما هو", "ما هي",
    "تفاصيل", "معلومات", "المزيد", "أيضا", "كذلك",
    "عن", "متعلق", "مثل", "tell", "give me", "do you have",
    "show me", "what is", "what are", "details", "information",
    "more", "also", "related", "similar", "about", "any other",
]

_VAGUE_PATTERNS: List[str] = [
    "تفاصيل", "معلومات", "اختصر", "ملخص",
    "المزيد", "أكثر", "tell me", "give me",
    "hello", "hi", "مرحبا", "ما هذا", "ما هو", "what is", "","...","?","!",".",","
]

_SPECIFIC_KEYWORDS: List[str] = [
    "قانون", "قوانين", "مرسوم", "مراسيم", "تشريع",
    "استثمار", "ضريبة", "ضرائب", "رسم", "رسوم",
    "مناقصات", "عطاء", "عطاءات", "مشروع", "مشاريع",
    "عقد", "اتفاقية", "إجراء", "شروط", "متطلبات",
    "إغاثة", "تعويض", "حماية", "حقوق", "التزامات",
    "صحية", "صحي", "صحة", "كهرباء", "كهربائي", "طاقة",
    "investment", "law", "tax", "decree", "contract",
    "tender", "tenders", "agreement", "procedure", "requirements", "rights",
]


def is_followup_question(question: str) -> bool:
    """Detect if *question* is a genuine follow-up (asks ABOUT previous results)."""
    q_lower = question.lower()
    if any(p in q_lower for p in _FOLLOWUP_PATTERNS):
        return True

    # Single-keyword questions (e.g. "الضرائب والرسوم") are new queries;
    # follow-ups usually have a verb or question-word.
    if len(question.split()) <= 2 and "ما" not in question and "هل" not in question:
        return False

    return False


def keyword_bonus(question: str, content: str) -> float:
    """Return 0–1 bonus based on how many question words appear in *content*."""
    q_words = question.split()
    hits = sum(1 for w in q_words if w in content)
    return min(hits / 10.0, 1.0)


def is_vague_question(question: str) -> bool:
    """Reject questions that are too vague to answer meaningfully."""
    q_lower = question.lower().strip()

    has_vague_pattern = any(p in q_lower for p in _VAGUE_PATTERNS)
    has_specific_keyword = any(k in q_lower for k in _SPECIFIC_KEYWORDS)

    if has_vague_pattern and not has_specific_keyword:
        return True

    if q_lower in ["مرحبا", "hello", "hi", "ما هذا", "ما هو", "what is"]:
        return True

    return False


def check_confidence_threshold(
    sources: List[Dict[str, Any]],
    threshold: float = 30.0,
) -> bool:
    """``True`` when the best source meets the minimum similarity score."""
    if not sources:
        return False
    best_score = sources[0].get("percentage", 0) or 0
    return best_score >= threshold


# ── Prompt builder ───────────────────────────────────────────────────

def build_prompt(
    question: str,
    sources: List[Dict[str, Any]],
    history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Assemble a RAG prompt from *sources* and optional *chat_history*."""
    history_text = ""
    if history:
        for message in history[-8:]:
            role = message.get("role", "user")
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            history_text += (
                f"{'ASSISTANT' if role == 'assistant' else 'USER'}: {content}\n"
            )
        if history_text:
            history_text += "\n"

    sources_text = "".join(
        f"SOURCE {idx}: {source.get('excerpt', '')}\n"
        for idx, source in enumerate(sources, start=1)
    )

    return (
        "Use only the following sources to answer the latest user question. "
        "Keep the answer concise and in the same language as the question.\n\n"
        f"{history_text}{sources_text}"
        f"QUESTION:\n{question}"
    )
