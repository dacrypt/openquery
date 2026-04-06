"""Tests for co.anm — ANM mining registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAnmResult:
    def test_defaults(self):
        from openquery.models.co.anm import AnmResult

        r = AnmResult()
        assert r.search_term == ""
        assert r.title_number == ""
        assert r.holder == ""
        assert r.status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.anm import AnmResult

        r = AnmResult(
            search_term="IKN-123",
            title_number="IKN-123",
            holder="Minera Colombia SA",
            status="Vigente",
        )
        dumped = r.model_dump_json()
        restored = AnmResult.model_validate_json(dumped)
        assert restored.search_term == "IKN-123"
        assert restored.status == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.anm import AnmResult

        r = AnmResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestAnmSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.anm import AnmSource

        assert AnmSource().meta().name == "co.anm"

    def test_meta_country(self):
        from openquery.sources.co.anm import AnmSource

        assert AnmSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.anm import AnmSource

        assert DocumentType.CUSTOM in AnmSource().meta().supported_inputs


class TestAnmParseResult:
    def _make_input(self, title: str = "IKN-123") -> QueryInput:
        return QueryInput(
            document_number=title,
            document_type=DocumentType.CUSTOM,
            extra={"title_number": title},
        )

    def test_empty_term_raises(self):
        from openquery.sources.co.anm import AnmSource

        with pytest.raises(SourceError, match="co.anm"):
            AnmSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.co.anm import AnmSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "IKN-123\nTitular: Minera Colombia SA\nVigente"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = AnmSource().query(self._make_input())

        assert result.search_term == "IKN-123"
