"""Exception hierarchy for OpenQuery."""

from __future__ import annotations


class OpenQueryError(Exception):
    """Base exception for all OpenQuery errors."""


class SourceError(OpenQueryError):
    """Error from a data source (scraper)."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"[{source}] {message}")


class CaptchaError(SourceError):
    """Captcha solving failed."""

    def __init__(self, source: str, message: str = "Captcha solving failed") -> None:
        super().__init__(source, message)


class RateLimitError(OpenQueryError):
    """Rate limit exceeded for a source."""

    def __init__(self, source: str, retry_after: float | None = None) -> None:
        self.source = source
        self.retry_after = retry_after
        msg = f"Rate limit exceeded for {source}"
        if retry_after:
            msg += f" (retry after {retry_after:.1f}s)"
        super().__init__(msg)


class DocumentOCRError(OpenQueryError):
    """Document OCR extraction failed."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"[OCR:{source}] {message}")


class FaceVerificationError(OpenQueryError):
    """Face verification failed."""

    def __init__(self, message: str) -> None:
        super().__init__(f"[Face] {message}")


class CacheError(OpenQueryError):
    """Cache backend error."""
