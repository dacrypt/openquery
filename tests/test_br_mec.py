"""Tests for br.mec — MEC university accreditation."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMecResult:
    def test_defaults(self):
        from openquery.models.br.mec import MecResult

        r = MecResult()
        assert r.search_term == ""
        assert r.institution_name == ""
        assert r.accreditation_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.mec import MecResult

        r = MecResult(
            search_term="USP",
            institution_name="Universidade de São Paulo",
            accreditation_status="Credenciada",
        )
        dumped = r.model_dump_json()
        restored = MecResult.model_validate_json(dumped)
        assert restored.search_term == "USP"
        assert restored.accreditation_status == "Credenciada"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.mec import MecResult

        r = MecResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestMecSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.mec import MecSource

        assert MecSource().meta().name == "br.mec"

    def test_meta_country(self):
        from openquery.sources.br.mec import MecSource

        assert MecSource().meta().country == "BR"

    def test_meta_supports_custom(self):
        from openquery.sources.br.mec import MecSource

        assert DocumentType.CUSTOM in MecSource().meta().supported_inputs

    def test_meta_requires_browser(self):
        from openquery.sources.br.mec import MecSource

        assert MecSource().meta().requires_browser is True


class TestMecParseResult:
    def _make_input(self, name: str = "USP") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"institution_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.br.mec import MecSource

        with pytest.raises(SourceError, match="br.mec"):
            MecSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.br.mec import MecSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "USP — Universidade de São Paulo\nCredenciada"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = MecSource().query(self._make_input())

        assert result.search_term == "USP"
        assert isinstance(result.queried_at, datetime)
