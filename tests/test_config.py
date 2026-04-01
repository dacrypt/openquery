"""Tests for configuration management."""

from __future__ import annotations

from openquery.config import Settings, get_settings


class TestSettings:
    def test_default_values(self):
        s = Settings()
        assert s.host == "0.0.0.0"
        assert s.port == 8000
        assert s.api_key == ""
        assert s.cache_backend == "memory"
        assert s.cache_ttl_default == 3600
        assert s.browser_headless is True
        assert s.browser_timeout == 30.0
        assert s.rate_limit_enabled is True
        assert s.rate_limit_default_rpm == 10
        assert s.log_level == "INFO"
        assert s.captcha_solver == "ocr"

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("OPENQUERY_PORT", "9000")
        monkeypatch.setenv("OPENQUERY_API_KEY", "test-key-123")
        monkeypatch.setenv("OPENQUERY_BROWSER_HEADLESS", "false")
        s = Settings()
        assert s.port == 9000
        assert s.api_key == "test-key-123"
        assert s.browser_headless is False

    def test_cache_backend_env(self, monkeypatch):
        monkeypatch.setenv("OPENQUERY_CACHE_BACKEND", "sqlite")
        s = Settings()
        assert s.cache_backend == "sqlite"

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("OPENQUERY_LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"


class TestGetSettings:
    def test_returns_settings_instance(self):
        s = get_settings()
        assert isinstance(s, Settings)
