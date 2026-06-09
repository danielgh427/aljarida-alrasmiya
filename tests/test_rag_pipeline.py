"""Tests for the RAG pipeline module."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.services.rag_pipeline import RagPipeline, _build_source, _fetch_latest_laws
from app.schemas.request import QuestionRequest


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for RagPipeline."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.execute.return_value = None

    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1, 0.2, 0.3]

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    }

    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test answer"))]
    )

    return {
        "cursor": mock_cursor,
        "model": mock_model,
        "collection": mock_collection,
        "openai": mock_openai,
    }


@pytest.fixture
def pipeline(mock_dependencies):
    """Create a RagPipeline instance with mock dependencies."""
    return RagPipeline(
        mysql_cursor=mock_dependencies["cursor"],
        chroma_model=mock_dependencies["model"],
        chroma_collection=mock_dependencies["collection"],
        openai_client=mock_dependencies["openai"],
        vector_db_path="/tmp/test_db",
    )


class TestBuildSource:
    def test_build_law_source(self):
        """Test building a law source dict."""
        meta = {
            "source_type": "law",
            "title": "Test Law",
            "law_number": "123",
            "law_type": "قانون",
            "law_date": "2024-01-01",
            "link": "http://example.com",
        }
        result = _build_source(1, meta, "Test content", 85.5)

        assert result["rank"] == 1
        assert result["source_type"] == "law"
        assert result["law_number"] == "123"
        assert result["percentage"] == 85.5

    def test_build_tender_source(self):
        """Test building a tender source dict."""
        meta = {
            "source_type": "tender",
            "title": "Test Tender",
            "summary": "Test summary",
            "document_location": "Beirut",
            "final_submission_deadline": "2024-12-31",
            "link": "http://example.com/tender",
        }
        result = _build_source(1, meta, "Tender content", 90.0)

        assert result["source_type"] == "tender"
        assert result["tender_title"] == "Test Tender"


class TestFetchLatestLaws:
    def test_fetch_empty(self):
        """Test fetching when no laws exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        context, sources = _fetch_latest_laws(mock_cursor)
        assert context == ""
        assert sources == []

    def test_fetch_multiple(self):
        """Test fetching multiple laws."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "title": "Law 1",
                "law_number": "100",
                "law_type": "قانون",
                "law_date": "2024-01-01",
                "link": "http://example.com/1",
                "content": "Content 1",
                "scraped_at": "2024-01-02",
            }
        ]

        context, sources = _fetch_latest_laws(mock_cursor)
        assert len(sources) == 1
        assert sources[0]["law_number"] == "100"


class TestRagPipelineAsk:
    @pytest.mark.asyncio
    async def test_ask_exact_search(self, pipeline, mock_dependencies):
        """Test ask endpoint with exact law number."""
        mock_dependencies["cursor"].fetchall.return_value = [
            {
                "title": "Exact Law",
                "law_number": "620",
                "law_type": "قانون",
                "law_date": "2024-01-01",
                "link": "http://example.com/620",
                "content": "Law content here",
            }
        ]

        request = QuestionRequest(question="ما هو القانون رقم 620؟")
        result = await pipeline.ask(request)

        assert "answer" in result
        assert "detected_category" in result

    @pytest.mark.asyncio
    async def test_ask_vague_question(self, pipeline):
        """Test ask endpoint with vague question."""
        request = QuestionRequest(question="hello")
        result = await pipeline.ask(request)

        assert "answer" in result
        assert "لم أتمكن" in result["answer"] or "عذراً" in result["answer"]

    @pytest.mark.asyncio
    async def test_ask_hybrid_search(self, pipeline, mock_dependencies):
        """Test ask endpoint with hybrid search."""
        mock_dependencies["collection"].query.return_value = {
            "documents": [["Test law content"]],
            "metadatas": [[{
                "source_type": "law",
                "title": "Hybrid Law",
                "law_number": "100",
                "law_type": "قانون",
                "law_date": "2024-01-01",
                "link": "http://example.com/100",
            }]],
            "distances": [[0.5]]
        }

        request = QuestionRequest(question="قوانين الاستثمار")
        result = await pipeline.ask(request)

        assert "answer" in result