"""Tests for pe.minem — MINEM mining concessions."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMinemResult:
    def test_defaults(self):
        from openquery.models.pe.minem import MinemResult

        r = MinemResult()
        assert r.search_term == ""
        assert r.concession_name == ""
        assert r.holder == ""
        assert r.status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pe.minem import MinemResult

        r = MinemResult(
            search_term="Concesión Aurora",
            concession_name="Concesión Aurora",
            holder="Minera Peru SA",
            status="Vigente",
        )
        dumped = r.model_dump_json()
        restored = MinemResult.model_validate_json(dumped)
        assert restored.search_term == "Concesión Aurora"
        assert restored.status == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.minem import MinemResult

        r = MinemResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestMinemSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pe.minem import MinemSource

        assert MinemSource().meta().name == "pe.minem"

    def test_meta_country(self):
        from openquery.sources.pe.minem import MinemSource

        assert MinemSource().meta().country == "PE"

    def test_meta_supports_custom(self):
        from openquery.sources.pe.minem import MinemSource

        assert DocumentType.CUSTOM in MinemSource().meta().supported_inputs


class TestMinemParseResult:
    def _make_input(self, name: str = "Concesión Aurora") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"concession_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.pe.minem import MinemSource

        with pytest.raises(SourceError, match="pe.minem"):
            MinemSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.pe.minem import MinemSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Concesión Aurora\nTitular: Minera Peru SA\nVigente"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = MinemSource().query(self._make_input())

        assert result.search_term == "Concesión Aurora"
