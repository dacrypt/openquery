"""Tests for br.ibama — IBAMA environmental sanctions."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestIbamaResult:
    def test_defaults(self):
        from openquery.models.br.ibama import IbamaResult

        r = IbamaResult()
        assert r.search_term == ""
        assert r.total_fines == 0
        assert r.fine_amount == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.ibama import IbamaResult

        r = IbamaResult(
            search_term="123.456.789-00",
            total_fines=2,
            fine_amount="R$ 5.000,00",
        )
        dumped = r.model_dump_json()
        restored = IbamaResult.model_validate_json(dumped)
        assert restored.search_term == "123.456.789-00"
        assert restored.total_fines == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.br.ibama import IbamaResult

        r = IbamaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestIbamaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.ibama import IbamaSource

        assert IbamaSource().meta().name == "br.ibama"

    def test_meta_country(self):
        from openquery.sources.br.ibama import IbamaSource

        assert IbamaSource().meta().country == "BR"

    def test_meta_supports_custom(self):
        from openquery.sources.br.ibama import IbamaSource

        assert DocumentType.CUSTOM in IbamaSource().meta().supported_inputs


class TestIbamaParseResult:
    def _make_input(self, cpf: str = "123.456.789-00") -> QueryInput:
        return QueryInput(
            document_number=cpf,
            document_type=DocumentType.CUSTOM,
            extra={"cpf_cnpj": cpf},
        )

    def test_empty_term_raises(self):
        from openquery.sources.br.ibama import IbamaSource

        with pytest.raises(SourceError, match="br.ibama"):
            IbamaSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.br.ibama import IbamaSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Valor: R$ 5.000,00\nMulta ambiental"
        mock_page.query_selector_all.return_value = [MagicMock(), MagicMock()]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = IbamaSource().query(self._make_input())

        assert result.search_term == "123.456.789-00"
        assert result.total_fines == 2
