"""Tests for br.cvm — CVM securities regulator company/fund lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test CvmResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.cvm import CvmResult

        r = CvmResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.cnpj == ""
        assert r.registration_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.cvm import CvmResult

        r = CvmResult(search_term="PETROBRAS", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "PETROBRAS" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.cvm import CvmResult

        r = CvmResult(
            search_term="PETROBRAS",
            company_name="PETRÓLEO BRASILEIRO S.A.",
            cnpj="33.000.167/0001-01",
            registration_status="Ativo",
            details={"Setor": "Petróleo e Gás"},
        )
        r2 = CvmResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "PETROBRAS"
        assert r2.company_name == "PETRÓLEO BRASILEIRO S.A."
        assert r2.cnpj == "33.000.167/0001-01"
        assert r2.registration_status == "Ativo"

    def test_queried_at_default(self):
        from openquery.models.br.cvm import CvmResult

        before = datetime.now()
        r = CvmResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test br.cvm source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.cvm import CvmSource

        meta = CvmSource().meta()
        assert meta.name == "br.cvm"

    def test_meta_country(self):
        from openquery.sources.br.cvm import CvmSource

        meta = CvmSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.cvm import CvmSource

        meta = CvmSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.br.cvm import CvmSource

        meta = CvmSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.cvm import CvmSource

        meta = CvmSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.br.cvm import CvmSource

        return CvmSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("Nenhuma empresa encontrada para a pesquisa")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.company_name == ""
        assert result.cnpj == ""

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultado da consulta")
        result = src._parse_result(page, "PETROBRAS")
        assert result.search_term == "PETROBRAS"

    def test_company_name_parsed(self):
        src = self._make_source()
        page = self._make_page("Empresa: PETRÓLEO BRASILEIRO S.A.\nSituação: Ativo")
        result = src._parse_result(page, "PETROBRAS")
        assert result.company_name == "PETRÓLEO BRASILEIRO S.A."

    def test_cnpj_parsed(self):
        src = self._make_source()
        page = self._make_page("CNPJ: 33.000.167/0001-01\nOutros dados")
        result = src._parse_result(page, "PETROBRAS")
        assert result.cnpj == "33.000.167/0001-01"

    def test_status_parsed(self):
        src = self._make_source()
        page = self._make_page("Situação: Ativo\nOutros dados")
        result = src._parse_result(page, "PETROBRAS")
        assert result.registration_status == "Ativo"

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.cvm import CvmSource

        src = CvmSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.br.cvm import CvmResult
        from openquery.sources.br.cvm import CvmSource

        src = CvmSource()
        mock_result = CvmResult(search_term="PETROBRAS")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="PETROBRAS"))
            m.assert_called_once_with("PETROBRAS", audit=False)
