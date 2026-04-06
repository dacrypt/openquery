"""Unit tests for Brazil CNES health facility registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.cnes import CnesResult
from openquery.sources.br.cnes import CnesSource


class TestCnesResult:
    """Test CnesResult model."""

    def test_default_values(self):
        data = CnesResult()
        assert data.search_term == ""
        assert data.facility_name == ""
        assert data.cnes_code == ""
        assert data.facility_type == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CnesResult(
            search_term="Hospital Central",
            facility_name="Hospital Central SP",
            cnes_code="1234567",
            facility_type="Hospital Geral",
            status="Ativo",
        )
        json_str = data.model_dump_json()
        restored = CnesResult.model_validate_json(json_str)
        assert restored.search_term == "Hospital Central"
        assert restored.cnes_code == "1234567"
        assert restored.facility_type == "Hospital Geral"

    def test_audit_excluded_from_json(self):
        data = CnesResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCnesSourceMeta:
    """Test CnesSource metadata."""

    def test_meta_name(self):
        source = CnesSource()
        assert source.meta().name == "br.cnes"

    def test_meta_country(self):
        source = CnesSource()
        assert source.meta().country == "BR"

    def test_meta_requires_browser(self):
        source = CnesSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = CnesSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CnesSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CnesSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test CnesSource._parse_result parsing logic."""

    def test_parse_found(self):
        source = CnesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nome: Hospital Central SP\n"
            "CNES: 1234567\n"
            "Tipo: Hospital Geral\n"
            "Situacao: Ativo\n"
            "Estabelecimento habilitado\n"
        )
        result = source._parse_result(mock_page, "Hospital Central")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = CnesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Nenhum resultado encontrado."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False
        assert result.status == "Nao encontrado"

    def test_query_requires_search_term(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = CnesSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "br.cnes" in str(e)
