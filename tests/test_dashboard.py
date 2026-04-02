"""Tests for dashboard static files."""

from __future__ import annotations

import pytest

from openquery.server.app import create_app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    app = create_app()
    return TestClient(app)


class TestDashboardStatic:
    """Test dashboard static files are served."""

    def test_index_html(self, client):
        res = client.get("/dashboard")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "OpenQuery" in res.text

    def test_style_css(self, client):
        res = client.get("/dashboard/style.css")
        assert res.status_code == 200
        assert "text/css" in res.headers["content-type"]

    def test_app_js(self, client):
        res = client.get("/dashboard/app.js")
        assert res.status_code == 200
        assert "javascript" in res.headers["content-type"]


class TestAPIEndpoints:
    """Test API endpoints used by dashboard."""

    def test_health(self, client):
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "sources_total" in data

    def test_sources_health(self, client):
        res = client.get("/api/v1/sources/health")
        assert res.status_code == 200
        data = res.json()
        assert "sources" in data
        assert "total_sources" in data
