"""ChromaDB vector-store — single entry-point for (re)building the index.

Run stand-alone:
    python -m services.embeddings.vector_store

Imports are kept lazy so the module loads fast and the embedding model is only
touched inside ``store_vectors()`` (triggered by the ``__main__`` guard).
"""
from __future__ import annotations
import sys
import os

# Project root on sys.path (needed when run as ``python vector_store.py``
# from the repo root instead of ``python -m …``)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import logging
import chromadb
from config import VECTOR_DB_PATH
from services.embeddings.rag_engine import generate_all_embeddings


logger = __import__("logging").getLogger(__name__)


# ── Lazy ChromaDB client ───────────────────────────────────────────

def _get_collection() -> chromadb.Collection:
    """Return the persistent ChromaDB collection (created on first call)."""
    client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    return client.get_or_create_collection("rag_collection")


# ── Public API ─────────────────────────────────────────────────────

def store_vectors() -> None:
    """Regenerate the entire vector database from MySQL data."""
    logger.info("Starting vector database regeneration...")

    collection = _get_collection()

    # Clear old data
    existing = collection.get()
    if existing["ids"]:
        logger.info("Clearing %d existing documents...", len(existing["ids"]))
        collection.delete(ids=existing["ids"])

    # Generate fresh embeddings
    all_documents, all_embeddings, all_ids, all_metadatas = generate_all_embeddings()

    if not all_documents:
        logger.warning("No documents to store — MySQL may be empty.")
        return

    # Validate metadata types (ChromaDB requires str | int | float | bool)
    bad = [
        (i, k, type(v), v)
        for i, meta in enumerate(all_metadatas)
        for k, v in meta.items()
        if not isinstance(v, (str, int, float, bool))
    ]
    if bad:
        for i, k, t, v in bad:
            logger.error("BAD METADATA -> row %d, key=%r, type=%s, value=%r", i, k, t, v)
        return

    # Upsert
    logger.info("Storing %d documents in vector database...", len(all_documents))
    collection.add(
        documents=all_documents,
        embeddings=all_embeddings,
        ids=all_ids,
        metadatas=all_metadatas,
    )

    # Verify
    final_count = collection.count()
    law_count    = sum(1 for m in all_metadatas if m.get("source_type") == "law")
    tender_count = sum(1 for m in all_metadatas if m.get("source_type") == "tender")

    logger.info("Successfully stored %d documents in vector database.", final_count)
    logger.info("  - Laws   : %d", law_count)
    logger.info("  - Tenders: %d", tender_count)


# ── Entry-point ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store_vectors()
    logger.info("Vector database regeneration completed successfully!")
