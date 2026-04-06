"""Tests for br.tcu — TCU government sanctions (licitantes inidôneos)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestBrTcuResult:
    def test_defaults(self):
        from openquery.models.br.tcu import BrTcuResult

        r = BrTcuResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.cnpj == ""
        assert r.sanction_status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.tcu import BrTcuResult

        r = BrTcuResult(
            search_term="Empresa Teste",
            company_name="Empresa Teste Ltda",
            cnpj="12345678000195",
            sanction_status="sanctioned",
        )
        restored = BrTcuResult.model_validate_json(r.model_dump_json())
        assert restored.company_name == "Empresa Teste Ltda"
        assert restored.sanction_status == "sanctioned"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.tcu import BrTcuResult

        r = BrTcuResult(audit="evidence")
        assert "audit" not in r.model_dump()


class TestBrTcuSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().name == "br.tcu"

    def test_meta_country(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().requires_browser is True

    def test_meta_no_captcha(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().rate_limit_rpm == 10


class TestBrTcuParseResult:
    def test_missing_search_raises(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_parse_sanctioned(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        page = MagicMock()
        page.inner_text.return_value = (
            "Resultado da consulta\n"
            "Razão Social: Empresa Corrupta SA\n"
            "CNPJ: 12345678000195\n"
            "Declarado inidôneo pelo TCU"
        )
        result = src._parse_result(page, "Empresa Corrupta SA")
        assert result.company_name == "Empresa Corrupta SA"
        assert result.cnpj == "12345678000195"
        assert result.sanction_status == "sanctioned"

    def test_parse_clear(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        page = MagicMock()
        page.inner_text.return_value = "Não foram encontrados resultados para a busca."
        result = src._parse_result(page, "Empresa Limpa")
        assert result.sanction_status == "clear"

    def test_parse_no_details(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        page = MagicMock()
        page.inner_text.return_value = "Página de consulta de licitantes"
        result = src._parse_result(page, "test")
        assert result.company_name == ""
        assert result.sanction_status == "clear"


@pytest.mark.integration
class TestBrTcuIntegration:
    def test_query_company(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="Empresa Teste",
            )
        )
        assert isinstance(result.sanction_status, str)
