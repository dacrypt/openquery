"""Tests for core.browser — BrowserManager (mocked Playwright)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openquery.core.browser import BrowserManager


class TestBrowserManagerInit:
    def test_default_params(self):
        bm = BrowserManager()
        assert bm._headless is True
        assert bm._timeout == 30.0

    def test_custom_params(self):
        bm = BrowserManager(headless=False, timeout=60.0)
        assert bm._headless is False
        assert bm._timeout == 60.0


class TestBrowserFetch:
    """Test browser_fetch and browser_fetch_json with a mock page."""

    def _make_page(self, evaluate_return):
        page = MagicMock()
        page.evaluate.return_value = evaluate_return
        return page

    def test_get_request(self):
        bm = BrowserManager()
        page = self._make_page({"status": 200, "body": '{"result": "ok"}'})
        result = bm.browser_fetch(page, "https://api.example.com/data")
        assert result["status"] == 200
        assert result["body"] == {"result": "ok"}
        page.evaluate.assert_called_once()

    def test_post_request_with_body(self):
        bm = BrowserManager()
        page = self._make_page({"status": 201, "body": '{"id": 42}'})
        result = bm.browser_fetch(
            page,
            "https://api.example.com/create",
            method="POST",
            body={"name": "test"},
        )
        assert result["status"] == 201
        assert result["body"] == {"id": 42}
        # Check that the JS included the body
        js_code = page.evaluate.call_args[0][0]
        assert "POST" in js_code

    def test_custom_headers(self):
        bm = BrowserManager()
        page = self._make_page({"status": 200, "body": '{"ok": true}'})
        bm.browser_fetch(
            page,
            "https://api.example.com/auth",
            method="GET",
            body={"token": "abc"},
            headers={"Authorization": "Bearer xyz"},
        )
        js_code = page.evaluate.call_args[0][0]
        assert "Authorization" in js_code

    def test_non_json_response(self):
        bm = BrowserManager()
        page = self._make_page({"status": 200, "body": "plain text response"})
        result = bm.browser_fetch(page, "https://example.com")
        assert result["status"] == 200
        assert result["body"] == "plain text response"
        assert result["raw"] == "plain text response"

    def test_empty_body(self):
        bm = BrowserManager()
        page = self._make_page({"status": 204, "body": ""})
        result = bm.browser_fetch(page, "https://example.com/delete")
        assert result["status"] == 204

    def test_browser_fetch_json(self):
        bm = BrowserManager()
        page = MagicMock()
        page.evaluate.return_value = {"items": [1, 2, 3]}
        result = bm.browser_fetch_json(page, "https://api.example.com/items")
        assert result == {"items": [1, 2, 3]}


class TestBrowserPage:
    """Test the page() context manager with mocked Playwright."""

    @patch("openquery.core.browser._get_sync_playwright")
    def test_page_context_manager_no_url(self, mock_pw_factory):
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        sync_playwright = mock_pw_factory.return_value
        sync_playwright_cm = sync_playwright.return_value
        sync_playwright_cm.__enter__ = MagicMock(return_value=mock_pw)
        sync_playwright_cm.__exit__ = MagicMock(return_value=False)
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        bm = BrowserManager(headless=True, timeout=10.0)
        with bm.page() as page:
            assert page is mock_page
            page.set_default_timeout.assert_called_with(10000)  # 10s * 1000
            # No goto since no URL
            page.goto.assert_not_called()

        mock_browser.close.assert_called_once()

    @patch("openquery.core.browser._get_sync_playwright")
    def test_page_context_manager_with_url(self, mock_pw_factory):
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        sync_playwright = mock_pw_factory.return_value
        sync_playwright_cm = sync_playwright.return_value
        sync_playwright_cm.__enter__ = MagicMock(return_value=mock_pw)
        sync_playwright_cm.__exit__ = MagicMock(return_value=False)
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        bm = BrowserManager(headless=True, timeout=15.0)
        with bm.page(url="https://example.com") as page:
            page.goto.assert_called_once_with(
                "https://example.com",
                wait_until="domcontentloaded",
                timeout=15000,
            )

    @patch("openquery.core.browser._get_sync_playwright")
    def test_browser_closes_on_exception(self, mock_pw_factory):
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        sync_playwright = mock_pw_factory.return_value
        sync_playwright_cm = sync_playwright.return_value
        sync_playwright_cm.__enter__ = MagicMock(return_value=mock_pw)
        sync_playwright_cm.__exit__ = MagicMock(return_value=False)
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        bm = BrowserManager()
        with pytest.raises(RuntimeError):
            with bm.page() as _page:
                raise RuntimeError("test error")

        mock_browser.close.assert_called_once()
