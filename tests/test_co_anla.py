"""Tests for co.anla — ANLA environmental licenses."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAnlaResult:
    def test_defaults(self):
        from openquery.models.co.anla import AnlaResult

        r = AnlaResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.license_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.anla import AnlaResult

        r = AnlaResult(
            search_term="Ecopetrol",
            company_name="Ecopetrol SA",
            license_status="Vigente",
        )
        dumped = r.model_dump_json()
        restored = AnlaResult.model_validate_json(dumped)
        assert restored.search_term == "Ecopetrol"
        assert restored.license_status == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.anla import AnlaResult

        r = AnlaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestAnlaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.anla import AnlaSource

        assert AnlaSource().meta().name == "co.anla"

    def test_meta_country(self):
        from openquery.sources.co.anla import AnlaSource

        assert AnlaSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.anla import AnlaSource

        assert DocumentType.CUSTOM in AnlaSource().meta().supported_inputs


class TestAnlaParseResult:
    def _make_input(self, name: str = "Ecopetrol") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"company_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.co.anla import AnlaSource

        with pytest.raises(SourceError, match="co.anla"):
            AnlaSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.co.anla import AnlaSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Ecopetrol SA\nVigente"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = AnlaSource().query(self._make_input())

        assert result.search_term == "Ecopetrol"
