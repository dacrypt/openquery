"""Extended API endpoint tests — query, sources, health, auth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from openquery.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


# ===========================================================================
# Health endpoint
# ===========================================================================


class TestHealthEndpoint:
    def test_health_has_version(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_has_cache_stats(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "cache" in data
        assert "backend" in data["cache"]


# ===========================================================================
# Sources endpoint
# ===========================================================================


class TestSourcesEndpoint:
    def test_many_sources_listed(self, client):
        resp = client.get("/api/v1/sources")
        data = resp.json()
        names = [s["name"] for s in data["sources"]]
        assert len(names) >= 13

    def test_source_has_required_fields(self, client):
        resp = client.get("/api/v1/sources")
        for src in resp.json()["sources"]:
            assert "name" in src
            assert "display_name" in src
            assert "country" in src
            assert "supported_inputs" in src
            assert len(src["supported_inputs"]) >= 1

    def test_all_sources_have_country(self, client):
        resp = client.get("/api/v1/sources")
        for src in resp.json()["sources"]:
            assert src["country"]


# ===========================================================================
# Query endpoint
# ===========================================================================


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
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == "unknown_source"

    def test_invalid_document_type(self, client):
        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.simit",
                "document_type": "invalid",
                "document_number": "123",
            },
        )
        # Pydantic should reject invalid enum value
        assert resp.status_code == 422

    def test_missing_required_fields(self, client):
        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.simit",
            },
        )
        assert resp.status_code == 422

    @patch("openquery.server.routes.query.get_source")
    def test_successful_query(self, mock_get_source, client):
        from pydantic import BaseModel

        class FakeResult(BaseModel):
            placa: str = "ABC123"
            total: int = 1

        mock_source = MagicMock()
        mock_source.query.return_value = FakeResult()
        mock_get_source.return_value = mock_source

        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.vehiculos",
                "document_type": "placa",
                "document_number": "ABC123",
            },
        )
        data = resp.json()
        assert data["ok"] is True
        assert data["data"]["placa"] == "ABC123"
        assert data["latency_ms"] >= 0

    @patch("openquery.server.routes.query.get_source")
    def test_source_exception(self, mock_get_source, client):
        mock_source = MagicMock()
        mock_source.query.side_effect = RuntimeError("network error")
        mock_get_source.return_value = mock_source

        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.simit",
                "document_type": "cedula",
                "document_number": "12345",
            },
        )
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == "RuntimeError"

    @patch("openquery.server.routes.query.get_source")
    def test_captcha_error_is_retryable(self, mock_get_source, client):
        from openquery.exceptions import CaptchaError

        mock_source = MagicMock()
        mock_source.query.side_effect = CaptchaError("co.runt", "Captcha failed")
        mock_get_source.return_value = mock_source

        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.runt",
                "document_type": "placa",
                "document_number": "ABC123",
            },
        )
        data = resp.json()
        assert data["ok"] is False
        assert data["retryable"] is True

    @patch("openquery.server.routes.query.get_source")
    @patch("openquery.server.routes.query.get_cache")
    def test_cache_hit(self, mock_cache_fn, mock_get_source, client):
        cache = MagicMock()
        cache.get.return_value = {"placa": "ABC123", "cached": True}
        mock_cache_fn.return_value = cache

        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.vehiculos",
                "document_type": "placa",
                "document_number": "ABC123",
            },
        )
        data = resp.json()
        assert data["ok"] is True
        assert data["cached"] is True
        # Source should NOT be called
        mock_get_source.return_value.query.assert_not_called()

    @patch("openquery.server.routes.query.get_source")
    @patch("openquery.server.routes.query.get_cache")
    def test_bypass_cache(self, mock_cache_fn, mock_get_source, client):
        from pydantic import BaseModel

        class FakeResult(BaseModel):
            total: int = 1

        cache = MagicMock()
        cache.get.return_value = {"total": 0}  # Stale cache
        mock_cache_fn.return_value = cache

        mock_source = MagicMock()
        mock_source.query.return_value = FakeResult()
        mock_get_source.return_value = mock_source

        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.vehiculos",
                "document_type": "placa",
                "document_number": "ABC123",
                "bypass_cache": True,
            },
        )
        data = resp.json()
        assert data["ok"] is True
        assert data["cached"] is False
        # Source SHOULD be called despite cache having data
        mock_source.query.assert_called_once()

    @patch("openquery.server.routes.query.get_rate_limiter")
    @patch("openquery.server.routes.query.get_source")
    @patch("openquery.server.routes.query.get_cache")
    def test_rate_limit_rejection(self, mock_cache_fn, mock_get_source, mock_limiter_fn, client):
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        limiter = MagicMock()
        limiter.is_allowed.return_value = False
        mock_limiter_fn.return_value = limiter

        mock_get_source.return_value = MagicMock()

        resp = client.post(
            "/api/v1/query",
            json={
                "source": "co.simit",
                "document_type": "cedula",
                "document_number": "123",
            },
        )
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == "rate_limited"
        assert data["retryable"] is True


# ===========================================================================
# Cache key generation
# ===========================================================================


class TestCacheKey:
    def test_make_key(self):
        from openquery.core.cache import make_key

        key = make_key("co.simit", "cedula", "12345678")
        assert key == "openquery:co.simit:cedula:12345678"

    def test_different_inputs_different_keys(self):
        from openquery.core.cache import make_key

        k1 = make_key("co.simit", "cedula", "111")
        k2 = make_key("co.simit", "cedula", "222")
        assert k1 != k2

    def test_different_sources_different_keys(self):
        from openquery.core.cache import make_key

        k1 = make_key("co.simit", "cedula", "111")
        k2 = make_key("co.runt", "cedula", "111")
        assert k1 != k2
