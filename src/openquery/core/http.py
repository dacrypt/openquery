"""HTTP client with SSL bypass, retry, and user-agent rotation.

Provides a configured httpx.Client for API-based sources that don't
need a full browser. Respects OPENQUERY_SSL_VERIFY for government
sites with expired or self-signed certificates.
"""

from __future__ import annotations

import logging
import random

import httpx

logger = logging.getLogger(__name__)

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
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
    ),
]


def get_client(timeout: float = 30.0, **kwargs: object) -> httpx.Client:
    """Get a configured httpx client with SSL bypass, UA rotation, and redirects.

    Args:
        timeout: Request timeout in seconds.
        **kwargs: Additional kwargs passed to httpx.Client.

    Returns:
        Configured httpx.Client instance.
    """
    from openquery.config import get_settings

    settings = get_settings()

    if not settings.ssl_verify:
        logger.debug("SSL verification disabled (OPENQUERY_SSL_VERIFY=false)")

    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=settings.ssl_verify,
        headers={
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        },
        **kwargs,
    )
