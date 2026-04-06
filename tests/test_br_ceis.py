"""Unit tests for Brazil CEIS sanctioned companies source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.ceis import CeisResult
from openquery.sources.br.ceis import CeisSource


class TestCeisResult:
    """Test CeisResult model."""

    def test_default_values(self):
        data = CeisResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.cnpj == ""
        assert data.sanction_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CeisResult(
            search_term="Empresa Fraudulenta",
            company_name="Empresa Fraudulenta Ltda",
            cnpj="12345678000195",
            sanction_status="Sancionado",
        )
        json_str = data.model_dump_json()
        restored = CeisResult.model_validate_json(json_str)
        assert restored.search_term == "Empresa Fraudulenta"
        assert restored.cnpj == "12345678000195"
        assert restored.sanction_status == "Sancionado"

    def test_audit_excluded_from_json(self):
        data = CeisResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCeisSourceMeta:
    """Test CeisSource metadata."""

    def test_meta_name(self):
        source = CeisSource()
        assert source.meta().name == "br.ceis"

    def test_meta_country(self):
        source = CeisSource()
        assert source.meta().country == "BR"

    def test_meta_requires_browser(self):
        source = CeisSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = CeisSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CeisSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CeisSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test CeisSource._parse_result parsing logic."""

    def test_parse_sanctioned(self):
        source = CeisSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nome: Empresa Fraudulenta Ltda\n"
            "CNPJ: 12.345.678/0001-95\n"
            "Situacao: Sancionado inidone suspenso\n"
        )
        result = source._parse_result(mock_page, "12345678000195")
        assert result.details["is_sanctioned"] is True

    def test_parse_not_found(self):
        source = CeisSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Nenhum resultado encontrado."
        result = source._parse_result(mock_page, "00000000000000")
        assert result.details["is_sanctioned"] is False
        assert result.sanction_status == "Nao encontrado"

    def test_query_requires_search_term(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = CeisSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "br.ceis" in str(e)
