"""Tests for OpenQuery exception hierarchy."""

from __future__ import annotations

from openquery.exceptions import (
    CacheError,
    CaptchaError,
    OpenQueryError,
    RateLimitError,
    SourceError,
)


class TestOpenQueryError:
    def test_base_exception(self):
        err = OpenQueryError("something went wrong")
        assert str(err) == "something went wrong"
        assert isinstance(err, Exception)


class TestSourceError:
    def test_message_format(self):
        err = SourceError("co.simit", "connection timeout")
        assert str(err) == "[co.simit] connection timeout"

    def test_source_attribute(self):
        err = SourceError("co.runt", "captcha failed")
        assert err.source == "co.runt"

    def test_inherits_openquery_error(self):
        err = SourceError("co.policia", "query failed")
        assert isinstance(err, OpenQueryError)
        assert isinstance(err, Exception)


class TestCaptchaError:
    def test_default_message(self):
        err = CaptchaError("co.runt")
        assert "Captcha solving failed" in str(err)
        assert err.source == "co.runt"

    def test_custom_message(self):
        err = CaptchaError("co.runt", "OCR returned empty string")
        assert "OCR returned empty string" in str(err)

    def test_inherits_source_error(self):
        err = CaptchaError("co.runt")
        assert isinstance(err, SourceError)
        assert isinstance(err, OpenQueryError)


class TestRateLimitError:
    def test_without_retry_after(self):
        err = RateLimitError("co.simit")
        assert err.source == "co.simit"
        assert err.retry_after is None
        assert "Rate limit exceeded" in str(err)

    def test_with_retry_after(self):
        err = RateLimitError("co.simit", retry_after=5.0)
        assert err.retry_after == 5.0
        assert "retry after 5.0s" in str(err)

    def test_inherits_openquery_error(self):
        err = RateLimitError("co.simit")
        assert isinstance(err, OpenQueryError)
        # RateLimitError does NOT inherit from SourceError
        assert not isinstance(err, SourceError)


class TestCacheError:
    def test_basic(self):
        err = CacheError("redis connection refused")
        assert "redis connection refused" in str(err)
        assert isinstance(err, OpenQueryError)
