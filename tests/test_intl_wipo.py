"""Tests for intl.wipo — WIPO Global Brand Database trademark search."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIntlWipoResult — model tests
# ===========================================================================


class TestIntlWipoResult:
    def test_defaults(self):
        from openquery.models.intl.wipo import IntlWipoResult

        r = IntlWipoResult()
        assert r.search_term == ""
        assert r.total == 0
        assert r.trademarks == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.wipo import IntlWipoResult, WipoTrademark

        r = IntlWipoResult(
            search_term="APPLE",
            total=100,
            trademarks=[
                WipoTrademark(
                    name="APPLE", owner="Apple Inc.", jurisdiction="US", status="registered"
                )
            ],
        )
        restored = IntlWipoResult.model_validate_json(r.model_dump_json())
        assert restored.search_term == "APPLE"
        assert restored.total == 100
        assert restored.trademarks[0].owner == "Apple Inc."

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.wipo import IntlWipoResult

        r = IntlWipoResult(audit="evidence")
        assert "audit" not in r.model_dump()


class TestWipoTrademark:
    def test_defaults(self):
        from openquery.models.intl.wipo import WipoTrademark

        t = WipoTrademark()
        assert t.name == ""
        assert t.owner == ""
        assert t.jurisdiction == ""
        assert t.status == ""
        assert t.application_number == ""


# ===========================================================================
# TestIntlWipoSourceMeta
# ===========================================================================


class TestIntlWipoSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        assert IntlWipoSource().meta().name == "intl.wipo"

    def test_meta_country(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        assert IntlWipoSource().meta().country == "INTL"

    def test_meta_requires_browser(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        assert IntlWipoSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        assert IntlWipoSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        assert IntlWipoSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestIntlWipoParseResult — parsing logic
# ===========================================================================


class TestIntlWipoParseResult:
    def test_missing_name_raises(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        src = IntlWipoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_parse_page_with_results(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        src = IntlWipoSource()
        page = MagicMock()
        page.inner_text.return_value = "COCA-COLA 1,234 results found in the database"

        result = src._parse_page(page, "COCA-COLA")
        assert result.search_term == "COCA-COLA"
        assert result.total == 1234

    def test_parse_page_no_results(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        src = IntlWipoSource()
        page = MagicMock()
        page.inner_text.return_value = "No results found"

        result = src._parse_page(page, "XYZNONEXISTENT")
        assert result.total == 0
        assert result.trademarks == []

    def test_extra_name_used(self):
        from openquery.models.intl.wipo import IntlWipoResult
        from openquery.sources.intl.wipo import IntlWipoSource

        src = IntlWipoSource()
        called_with: list[str] = []

        def fake_query(name: str) -> IntlWipoResult:
            called_with.append(name)
            return IntlWipoResult(search_term=name)

        src._query = fake_query
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"name": "SAMSUNG"},
            )
        )
        assert called_with[0] == "SAMSUNG"


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestIntlWipoIntegration:
    def test_query_brand(self):
        from openquery.sources.intl.wipo import IntlWipoSource

        src = IntlWipoSource(headless=True)
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                extra={"name": "GOOGLE"},
            )
        )
        assert isinstance(result.search_term, str)
        assert result.total >= 0
