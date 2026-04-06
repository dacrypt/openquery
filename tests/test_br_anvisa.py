"""Tests for br.anvisa — ANVISA health product registry lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test AnvisaResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.anvisa import AnvisaResult

        r = AnvisaResult()
        assert r.search_term == ""
        assert r.product_name == ""
        assert r.registration_number == ""
        assert r.status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.anvisa import AnvisaResult

        r = AnvisaResult(search_term="DIPIRONA", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "DIPIRONA" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.anvisa import AnvisaResult

        r = AnvisaResult(
            search_term="DIPIRONA",
            product_name="DIPIRONA SÓDICA",
            registration_number="1234567890",
            status="Válido",
            details={"Empresa": "Lab XYZ"},
        )
        r2 = AnvisaResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "DIPIRONA"
        assert r2.product_name == "DIPIRONA SÓDICA"
        assert r2.registration_number == "1234567890"
        assert r2.status == "Válido"

    def test_queried_at_default(self):
        from openquery.models.br.anvisa import AnvisaResult

        before = datetime.now()
        r = AnvisaResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test br.anvisa source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.anvisa import AnvisaSource

        meta = AnvisaSource().meta()
        assert meta.name == "br.anvisa"

    def test_meta_country(self):
        from openquery.sources.br.anvisa import AnvisaSource

        meta = AnvisaSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.anvisa import AnvisaSource

        meta = AnvisaSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.br.anvisa import AnvisaSource

        meta = AnvisaSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.anvisa import AnvisaSource

        meta = AnvisaSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.br.anvisa import AnvisaSource

        return AnvisaSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("Nenhum registro encontrado para a pesquisa")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.product_name == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultado da consulta")
        result = src._parse_result(page, "DIPIRONA")
        assert result.search_term == "DIPIRONA"

    def test_product_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Produto: DIPIRONA SÓDICA\nSituação: Válido")
        result = src._parse_result(page, "DIPIRONA")
        assert result.product_name == "DIPIRONA SÓDICA"

    def test_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Situação: Válido\nOutros dados")
        result = src._parse_result(page, "DIPIRONA")
        assert result.status == "Válido"

    def test_registration_number_parsed(self):
        src = self._make_source()
        page = self._make_page("Número de Registro: 1234567890\nOutros")
        result = src._parse_result(page, "DIPIRONA")
        assert result.registration_number == "1234567890"

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.anvisa import AnvisaSource

        src = AnvisaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.br.anvisa import AnvisaResult
        from openquery.sources.br.anvisa import AnvisaSource

        src = AnvisaSource()
        mock_result = AnvisaResult(search_term="DIPIRONA")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="DIPIRONA"))
            m.assert_called_once_with("DIPIRONA", audit=False)
