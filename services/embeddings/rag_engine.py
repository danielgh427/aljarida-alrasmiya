"""Embedding-generation service — laws + tenders → ChromaDB-compatible tuples.

Split from the monolithic ``rag_chatbot.py`` so it can be run stand-alone
(``python -m services.embeddings.rag_engine``) or imported by
``vector_store.py`` without triggering the embedding model at import time.
"""
from __future__ import annotations

import logging
from typing import Any

from sentence_transformers import SentenceTransformer

from .fetch_laws import get_laws
from .fetch_tenders import get_tenders

logger = logging.getLogger(__name__)

# Model name used for *both* law and tender embeddings.
MODEL_NAME = "intfloat/multilingual-e5-small"

# Prefix required by the E5 model family for *queries* and *documents*.
E5_PASSAGE_PREFIX = "passage: "


# ── Model factory ──────────────────────────────────────────────────

def get_model() -> SentenceTransformer:
    """Lazily load and cache the embedding model (cheap after first call)."""
    if not hasattr(get_model, "_cached"):
        logger.info("Loading embedding model: %s", MODEL_NAME)
        get_model._cached = SentenceTransformer(MODEL_NAME)  # type: ignore[attr-defined]
    return get_model._cached  # type: ignore[return-value]


# ── Pure helpers ────────────────────────────────────────────────────

def _safe_str(value: Any) -> str:
    """Return a stripped string, or ``""`` when *value* is ``None`` / falsy."""
    if value is None:
        return ""
    return str(value).strip()


def _encode(text: str) -> list[float]:
    """Thin wrapper around :py:meth:`SentenceTransformer.encode`."""
    return get_model().encode(E5_PASSAGE_PREFIX + text).tolist()


# ── Law embeddings ──────────────────────────────────────────────────

def generate_law_embeddings() -> tuple[list[str], list[list[float]], list[str], list[dict[str, Any]]]:
    """Return ``(documents, embeddings, ids, metadatas)`` for every law in MySQL."""
    laws = get_laws()

    documents: list[str] = []
    embeddings: list[list[float]] = []
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for law in laws:
        title     = _safe_str(law.get("title"))
        law_number = _safe_str(law.get("law_number"))
        law_type  = _safe_str(law.get("law_type"))
        law_date  = _safe_str(law.get("law_date"))
        content   = _safe_str(law.get("content"))
        link      = _safe_str(law.get("link"))

        content_body = content or f"Legal document: {title}"

        passage = (
            f"Law Title: {title}\n"
            f"Law Number: {law_number}\n"
            f"Law Type: {law_type}\n"
            f"Law Date: {law_date}\n"
            f"Content: {content_body}"
        )

        documents.append(passage)
        embeddings.append(_encode(passage))
        ids.append(f"law_{law['id']}")

        metadatas.append({
            "source_type": "law",
            "title":       title,
            "law_number":  law_number,
            "law_type":    law_type,
            "law_date":    law_date,
            "content":     content_body[:1000],
            "link":        link,
        })

    logger.info("Generated %d law embeddings.", len(documents))
    return documents, embeddings, ids, metadatas


# ── Tender embeddings ───────────────────────────────────────────────

def generate_tender_embeddings() -> tuple[list[str], list[list[float]], list[str], list[dict[str, Any]]]:
    """Return ``(documents, embeddings, ids, metadatas)`` for every tender in MySQL."""
    tenders = get_tenders()

    documents: list[str] = []
    embeddings: list[list[float]] = []
    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for t in tenders:
        title   = _safe_str(t.get("title"))
        summary = _safe_str(t.get("summary"))
        loc     = _safe_str(t.get("document_location"))
        deadline = _safe_str(t.get("final_submission_deadline"))
        link    = _safe_str(t.get("link"))

        passage = (
            f"عنوان المناقصة: {title}\n"
            f"الوصف: {summary}\n"
            f"الموقع: {loc}\n"
            f"الموعد النهائي: {deadline}"
        )

        documents.append(passage)
        embeddings.append(_encode(passage))
        ids.append(f"tender_{t['id']}")

        metadatas.append({
            "source_type":               "tender",
            "title":                     title,
            "summary":                   summary,
            "document_location":         loc,
            "final_submission_deadline": deadline,
            "link":                      link,
        })

    logger.info("Generated %d tender embeddings.", len(documents))
    return documents, embeddings, ids, metadatas


# ── Combined ────────────────────────────────────────────────────────

def generate_all_embeddings() -> tuple[list[str], list[list[float]], list[str], list[dict[str, Any]]]:
    """Return concatenated ``(docs, embs, ids, metas)`` for laws + tenders."""
    l_docs, l_embs, l_ids, l_meta = generate_law_embeddings()
    t_docs, t_embs, t_ids, t_meta = generate_tender_embeddings()
    return (
        l_docs + t_docs,
        l_embs + t_embs,
        l_ids + t_ids,
        l_meta + t_meta,
    )
