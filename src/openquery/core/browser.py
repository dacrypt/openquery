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
import random
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Stealth launch args — reduce headless browser detection
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
]

_COUNTRY_LOCALES: dict[str, str] = {
    "CO": "es-CO",
    "AR": "es-AR",
    "MX": "es-MX",
    "CL": "es-CL",
    "PE": "es-PE",
    "EC": "es-EC",
    "VE": "es-VE",
    "BR": "pt-BR",
    "US": "en-US",
    "PA": "es-PA",
    "BO": "es-BO",
    "CR": "es-CR",
    "DO": "es-DO",
    "SV": "es-SV",
    "GT": "es-GT",
    "HN": "es-HN",
    "NI": "es-NI",
    "PY": "es-PY",
    "UY": "es-UY",
    "PR": "es-PR",
}

# Cookie consent banner selectors (common across many sites)
_COOKIE_SELECTORS = [
    "button[id*='accept' i]",
    "button[id*='cookie' i]",
    "button[class*='accept' i]",
    "button[class*='cookie' i]",
    ".accept-cookies",
    "#onetrust-accept-btn-handler",
    "button[aria-label*='accept' i]",
    "button[data-testid*='accept' i]",
]

# Cloudflare / Imperva challenge indicators
_CF_SELECTORS = [
    "#cf-browser-verification",
    "#challenge-platform",
    "#challenge-stage",
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


def _dismiss_cookie_banners(page: Any) -> None:
    """Attempt to dismiss cookie consent banners after page load.

    Waits up to 2s for banners to appear, then clicks the first matching button.
    Silently ignores errors — cookie dismissal is best-effort.
    """
    try:
        page.wait_for_timeout(2000)
        for selector in _COOKIE_SELECTORS:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click(timeout=2000)
                    logger.debug("Dismissed cookie banner: %s", selector)
                    return
            except Exception:
                continue
    except Exception:
        pass


def _wait_for_challenges(page: Any, timeout_ms: int = 10000) -> None:
    """Wait for Cloudflare/Akamai/Imperva challenge pages to resolve.

    Detects challenge indicators in title or DOM and waits up to timeout_ms
    for them to disappear. Also handles "Access Denied" / "Request unsuccessful"
    Imperva/Akamai blocks by waiting for the page to change.
    """
    try:
        title = (page.title() or "").lower()
        content = page.content()

        is_cf_challenge = (
            "just a moment" in title
            or any(page.query_selector(sel) for sel in _CF_SELECTORS)
        )
        is_imperva = (
            "access denied" in title
            or "request unsuccessful" in title
            or "incapsula incident" in content.lower()
        )

        if is_cf_challenge:
            logger.info("Cloudflare challenge detected — waiting up to %dms", timeout_ms)
            try:
                page.wait_for_function(
                    """() => {
                        const title = document.title.toLowerCase();
                        return !title.includes('just a moment')
                            && !document.querySelector('#cf-browser-verification')
                            && !document.querySelector('#challenge-platform');
                    }""",
                    timeout=timeout_ms,
                )
                logger.info("Cloudflare challenge resolved")
            except Exception:
                logger.warning("Cloudflare challenge did not resolve within %dms", timeout_ms)

        elif is_imperva:
            logger.info("Imperva/Akamai block detected — waiting up to %dms", timeout_ms)
            try:
                page.wait_for_function(
                    """() => {
                        const title = document.title.toLowerCase();
                        return !title.includes('access denied')
                            && !title.includes('request unsuccessful');
                    }""",
                    timeout=timeout_ms,
                )
                logger.info("Imperva/Akamai block resolved")
            except Exception:
                logger.warning("Imperva/Akamai block did not resolve within %dms", timeout_ms)

    except Exception:
        pass


class BrowserManager:
    """Manage browser lifecycle with stealth capabilities.

    Uses Patchright (patched Playwright) to bypass WAF/bot detection.
    Falls back to standard Playwright if Patchright is not available.

    Proxy support: set OPENQUERY_PROXY_URL to route traffic through a
    residential/rotating proxy for WAF bypass. Example:
        OPENQUERY_PROXY_URL=http://user:pass@proxy.example.com:8080
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: float = 30.0,
        proxy: str = "",
        locale: str = "",
        country: str = "",
    ) -> None:
        self._headless = headless
        self._timeout = timeout
        self._proxy = proxy
        # Resolve locale: explicit > country lookup > default en-US
        if locale:
            self._locale = locale
        elif country:
            self._locale = _COUNTRY_LOCALES.get(country.upper(), "en-US")
        else:
            self._locale = "en-US"

    def _resolve_proxy(self) -> str:
        """Resolve proxy URL from instance or config."""
        if self._proxy:
            return self._proxy
        from openquery.config import get_settings

        return get_settings().proxy_url

    def _build_launch_kwargs(self) -> dict[str, Any]:
        """Build chromium.launch() kwargs."""
        kwargs: dict[str, Any] = {
            "headless": self._headless,
            "args": _STEALTH_ARGS,
        }
        proxy_url = self._resolve_proxy()
        if proxy_url:
            kwargs["proxy"] = {"server": proxy_url}
            logger.info(
                "Using proxy: %s",
                proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url,
            )
        return kwargs

    def _build_context_kwargs(self) -> dict[str, Any]:
        """Build browser.new_context() kwargs."""
        return {
            "user_agent": random.choice(_USER_AGENTS),
            "viewport": {"width": 1920, "height": 1080},
            "locale": self._locale,
            "java_script_enabled": True,
        }

    @contextmanager
    def sync_context(self):
        """Yield a raw browser context within a managed stealth browser.

        Used by sources that manage their own page lifecycle (ctx.new_page()).
        Cookie banners and challenge detection are NOT auto-applied here —
        callers are responsible for page navigation and post-goto handling.

        Yields:
            A Playwright/Patchright BrowserContext object.
        """
        sync_playwright = _get_sync_playwright()
        launch_kwargs = self._build_launch_kwargs()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            try:
                context = browser.new_context(**self._build_context_kwargs())
                yield context
            finally:
                browser.close()

    @contextmanager
    def page(self, url: str | None = None, wait_until: str = "domcontentloaded"):
        """Get a browser page within a managed stealth context.

        After navigation, automatically:
        - Waits for Cloudflare/Imperva challenges to resolve
        - Dismisses cookie consent banners
        - Attempts auto-CAPTCHA solving if a solver is configured

        Args:
            url: If provided, navigates to this URL (useful for acquiring WAF cookies).
            wait_until: Playwright wait condition for navigation.

        Yields:
            A Playwright/Patchright Page object.
        """
        sync_playwright = _get_sync_playwright()
        launch_kwargs = self._build_launch_kwargs()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            try:
                context = browser.new_context(**self._build_context_kwargs())
                pg = context.new_page()
                pg.set_default_timeout(self._timeout * 1000)

                if url:
                    logger.info("Navigating to %s", url)
                    pg.goto(url, wait_until=wait_until, timeout=self._timeout * 1000)
                    _wait_for_challenges(pg)
                    _dismiss_cookie_banners(pg)
                    try:
                        from openquery.core.captcha_middleware import solve_page_captchas

                        solve_page_captchas(pg)
                    except Exception:
                        logger.debug("Auto-CAPTCHA: no captcha or no solver configured")

                yield pg
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
