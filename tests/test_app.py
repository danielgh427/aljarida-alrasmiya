"""Integration tests for the FastAPI application."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.fixture
def mock_pipeline():
    """Mock the RAG pipeline for testing endpoints."""
    with patch("app.main.pipeline") as mock:
        mock.ask = AsyncMock(return_value={
            "answer": "Test answer",
            "sources": [],
            "detected_category": "law"
        })
        yield mock


def test_root(mock_pipeline):
    """Test root endpoint returns expected message."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health(mock_pipeline):
    """Test health endpoint."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_endpoint(mock_pipeline):
    """Test /ask endpoint with valid request."""
    client = TestClient(app)
    response = client.post("/ask", json={"question": "What is law 123?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data


def test_ask_with_category(mock_pipeline):
    """Test /ask endpoint with category filter."""
    client = TestClient(app)
    response = client.post(
        "/ask",
        json={"question": "test question", "category": "law", "max_results": 5}
    )
    assert response.status_code == 200


def test_ask_invalid_request():
    """Test /ask endpoint with invalid request."""
    client = TestClient(app)
    response = client.post("/ask", json={})
    assert response.status_code == 422