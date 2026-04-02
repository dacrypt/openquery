"""Browser automation manager using Patchright (stealth Playwright).

Uses Patchright — a drop-in Playwright replacement that patches Chrome DevTools
Protocol leaks to avoid WAF/bot detection. Falls back to Playwright if
Patchright is not installed.

Provides two patterns:
1. DOM scraping — navigate, fill forms, parse elements (SIMIT pattern)
2. Browser fetch — use page.evaluate(fetch()) to make API calls with WAF cookies (RUNT pattern)
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Stealth launch args — reduce headless browser detection
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]


def _get_sync_playwright():
    """Get sync_playwright from patchright (preferred) or playwright (fallback)."""
    try:
        from patchright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        logger.debug("Patchright not installed, falling back to Playwright")
        from playwright.sync_api import sync_playwright
        return sync_playwright


class BrowserManager:
    """Manage browser lifecycle with stealth capabilities.

    Uses Patchright (patched Playwright) to bypass WAF/bot detection.
    Falls back to standard Playwright if Patchright is not available.
    """

    def __init__(self, headless: bool = True, timeout: float = 30.0) -> None:
        self._headless = headless
        self._timeout = timeout

    @contextmanager
    def page(self, url: str | None = None, wait_until: str = "domcontentloaded"):
        """Get a browser page within a managed stealth context.

        Args:
            url: If provided, navigates to this URL (useful for acquiring WAF cookies).
            wait_until: Playwright wait condition for navigation.

        Yields:
            A Playwright/Patchright Page object.
        """
        sync_playwright = _get_sync_playwright()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=self._headless,
                args=_STEALTH_ARGS,
            )
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                    locale="es-CO",
                    timezone_id="America/Bogota",
                )
                page = context.new_page()
                page.set_default_timeout(self._timeout * 1000)

                if url:
                    logger.info("Navigating to %s", url)
                    page.goto(url, wait_until=wait_until, timeout=self._timeout * 1000)

                yield page
            finally:
                browser.close()

    def browser_fetch(
        self,
        page: Any,
        url: str,
        method: str = "GET",
        body: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Execute a fetch() call inside the browser context.

        This bypasses WAF protections by using the browser's cookies/session.
        The RUNT WAF bypass pattern generalized.

        Args:
            page: Playwright page with active session.
            url: API URL to fetch.
            method: HTTP method.
            body: JSON body for POST/PUT requests.
            headers: Additional headers.

        Returns:
            Dict with 'status' and 'body' (parsed JSON or raw text).
        """
        fetch_headers = {"Content-Type": "application/json"}
        if headers:
            fetch_headers.update(headers)

        if body is not None:
            body_json = json.dumps(body)
            js = f"""async () => {{
                const r = await fetch('{url}', {{
                    method: '{method}',
                    headers: {json.dumps(fetch_headers)},
                    body: {json.dumps(body_json)},
                }});
                const text = await r.text();
                return {{ status: r.status, body: text }};
            }}"""
        else:
            js = f"""async () => {{
                const r = await fetch('{url}');
                const text = await r.text();
                return {{ status: r.status, body: text }};
            }}"""

        result = page.evaluate(js)

        status = result.get("status", 0)
        body_text = result.get("body", "")

        # Try to parse JSON
        try:
            parsed = json.loads(body_text)
        except (json.JSONDecodeError, TypeError):
            parsed = body_text

        return {"status": status, "body": parsed, "raw": body_text}

    def browser_fetch_json(self, page: Any, url: str) -> dict:
        """Fetch JSON from browser context (convenience for GET requests).

        Returns the parsed JSON directly.
        """
        js = f"""async () => {{
            const r = await fetch('{url}');
            const data = await r.json();
            return data;
        }}"""
        return page.evaluate(js)
