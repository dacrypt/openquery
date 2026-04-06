"""Tests for co.creg — CREG energy regulator."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCregResult:
    def test_defaults(self):
        from openquery.models.co.creg import CregResult

        r = CregResult()
        assert r.search_term == ""
        assert r.entity_name == ""
        assert r.regulation_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.creg import CregResult

        r = CregResult(
            search_term="Enel",
            entity_name="Enel Colombia SA ESP",
            regulation_status="Regulada",
        )
        dumped = r.model_dump_json()
        restored = CregResult.model_validate_json(dumped)
        assert restored.search_term == "Enel"
        assert restored.regulation_status == "Regulada"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.creg import CregResult

        r = CregResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestCregSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.creg import CregSource

        assert CregSource().meta().name == "co.creg"

    def test_meta_country(self):
        from openquery.sources.co.creg import CregSource

        assert CregSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.creg import CregSource

        assert DocumentType.CUSTOM in CregSource().meta().supported_inputs


class TestCregParseResult:
    def _make_input(self, name: str = "Enel") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"company_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.co.creg import CregSource

        with pytest.raises(SourceError, match="co.creg"):
            CregSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.co.creg import CregSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Enel Colombia SA ESP\nRegulada"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = CregSource().query(self._make_input())

        assert result.search_term == "Enel"
