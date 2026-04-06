"""Tests for mx.anuies — ANUIES university data."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAnuiesResult:
    def test_defaults(self):
        from openquery.models.mx.anuies import AnuiesResult

        r = AnuiesResult()
        assert r.search_term == ""
        assert r.institution_name == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.mx.anuies import AnuiesResult

        r = AnuiesResult(
            search_term="UNAM",
            institution_name="Universidad Nacional Autónoma de México",
        )
        dumped = r.model_dump_json()
        restored = AnuiesResult.model_validate_json(dumped)
        assert restored.search_term == "UNAM"
        assert restored.institution_name == "Universidad Nacional Autónoma de México"

    def test_audit_excluded_from_json(self):
        from openquery.models.mx.anuies import AnuiesResult

        r = AnuiesResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestAnuiesSourceMeta:
    def test_meta_name(self):
        from openquery.sources.mx.anuies import AnuiesSource

        assert AnuiesSource().meta().name == "mx.anuies"

    def test_meta_country(self):
        from openquery.sources.mx.anuies import AnuiesSource

        assert AnuiesSource().meta().country == "MX"

    def test_meta_supports_custom(self):
        from openquery.sources.mx.anuies import AnuiesSource

        assert DocumentType.CUSTOM in AnuiesSource().meta().supported_inputs


class TestAnuiesParseResult:
    def _make_input(self, name: str = "UNAM") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"institution_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.mx.anuies import AnuiesSource

        with pytest.raises(SourceError, match="mx.anuies"):
            AnuiesSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.mx.anuies import AnuiesSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "UNAM — Universidad Nacional Autónoma de México"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = AnuiesSource().query(self._make_input())

        assert result.search_term == "UNAM"
