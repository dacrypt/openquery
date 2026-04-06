"""Unit tests for FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from openquery.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestSourcesEndpoint:
    def test_sources_list(self, client):
        resp = client.get("/api/v1/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        names = [s["name"] for s in data["sources"]]
        assert "co.simit" in names
        assert "co.runt" in names


class TestQueryEndpoint:
    def test_unknown_source(self, client):
        resp = client.post(
            "/api/v1/query",
            json={
                "source": "xx.unknown",
                "document_type": "cedula",
                "document_number": "123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == "unknown_source"
