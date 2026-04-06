"""Tests for pe.oefa — OEFA environmental enforcement."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestOefaResult:
    def test_defaults(self):
        from openquery.models.pe.oefa import OefaResult

        r = OefaResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.total_sanctions == 0
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pe.oefa import OefaResult

        r = OefaResult(
            search_term="Minera XYZ",
            company_name="Minera XYZ SA",
            total_sanctions=3,
        )
        dumped = r.model_dump_json()
        restored = OefaResult.model_validate_json(dumped)
        assert restored.search_term == "Minera XYZ"
        assert restored.total_sanctions == 3

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.oefa import OefaResult

        r = OefaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestOefaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pe.oefa import OefaSource

        assert OefaSource().meta().name == "pe.oefa"

    def test_meta_country(self):
        from openquery.sources.pe.oefa import OefaSource

        assert OefaSource().meta().country == "PE"

    def test_meta_supports_custom(self):
        from openquery.sources.pe.oefa import OefaSource

        assert DocumentType.CUSTOM in OefaSource().meta().supported_inputs


class TestOefaParseResult:
    def _make_input(self, name: str = "Minera XYZ") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"company_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.pe.oefa import OefaSource

        with pytest.raises(SourceError, match="pe.oefa"):
            OefaSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.pe.oefa import OefaSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Minera XYZ SA\nSanción administrativa"
        mock_page.query_selector_all.return_value = [MagicMock(), MagicMock()]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = OefaSource().query(self._make_input())

        assert result.search_term == "Minera XYZ"
        assert result.total_sanctions == 2
