"""Tests for br.inss — INSS social security contribution lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestInssResult:
    """Test InssResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.inss import InssResult

        r = InssResult()
        assert r.cpf == ""
        assert r.contribution_status == ""
        assert r.benefit_type == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.inss import InssResult

        r = InssResult(cpf="12345678901", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "12345678901" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.inss import InssResult

        r = InssResult(
            cpf="12345678901",
            contribution_status="Regular",
            benefit_type="Aposentadoria",
            details={"Situação": "Ativo"},
        )
        r2 = InssResult.model_validate_json(r.model_dump_json())
        assert r2.cpf == "12345678901"
        assert r2.contribution_status == "Regular"
        assert r2.details["Situação"] == "Ativo"

    def test_queried_at_default(self):
        from openquery.models.br.inss import InssResult

        before = datetime.now()
        r = InssResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestInssSourceMeta:
    """Test br.inss source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.inss import InssSource

        assert InssSource().meta().name == "br.inss"

    def test_meta_country(self):
        from openquery.sources.br.inss import InssSource

        assert InssSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.inss import InssSource

        assert InssSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.br.inss import InssSource

        assert DocumentType.CUSTOM in InssSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.inss import InssSource

        assert InssSource().meta().rate_limit_rpm == 10


class TestInssParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, cpf: str = "12345678901"):
        from openquery.sources.br.inss import InssSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return InssSource()._parse_result(page, cpf)

    def test_cpf_preserved(self):
        assert self._parse("Dados", cpf="98765432100").cpf == "98765432100"

    def test_contribution_status_parsed(self):
        result = self._parse("Situação: Contribuinte Facultativo\nOutros")
        assert result.contribution_status == "Contribuinte Facultativo"

    def test_benefit_type_parsed(self):
        result = self._parse("Benefício: Aposentadoria por Tempo de Contribuição")
        assert result.benefit_type == "Aposentadoria por Tempo de Contribuição"

    def test_empty_body(self):
        result = self._parse("")
        assert result.cpf == "12345678901"
        assert result.contribution_status == ""

    def test_query_missing_cpf_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.inss import InssSource

        with pytest.raises(SourceError, match="CPF"):
            InssSource().query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
