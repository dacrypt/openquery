"""Tests for API key authentication middleware."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from openquery.server.app import create_app


class TestAuthDisabled:
    """When OPENQUERY_API_KEY is empty, auth is disabled."""

    def test_no_auth_needed(self):
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/v1/sources")
        assert resp.status_code == 200


class TestAuthEnabled:
    """When OPENQUERY_API_KEY is set, auth is enforced."""

    def _make_client(self):
        with patch("openquery.server.auth.get_settings") as mock:
            settings = mock.return_value
            settings.api_key = "test-secret-key"
            app = create_app()
        return TestClient(app)

    def test_missing_key_rejected(self):
        client = self._make_client()
        resp = client.get("/api/v1/sources")
        assert resp.status_code == 401
        assert resp.json()["error"] == "invalid_api_key"

    def test_wrong_key_rejected(self):
        client = self._make_client()
        resp = client.get(
            "/api/v1/sources",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_correct_header_key(self):
        client = self._make_client()
        resp = client.get(
            "/api/v1/sources",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 200

    def test_correct_query_param_key(self):
        client = self._make_client()
        resp = client.get("/api/v1/sources?api_key=test-secret-key")
        assert resp.status_code == 200

    def test_health_bypasses_auth(self):
        client = self._make_client()
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_docs_bypass_auth(self):
        client = self._make_client()
        resp = client.get("/docs")
        # docs endpoint may redirect, but shouldn't 401
        assert resp.status_code != 401
