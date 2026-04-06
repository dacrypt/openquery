"""Unit tests for Peru DIGEMID drug registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.digemid import DigemidResult
from openquery.sources.pe.digemid import DigemidSource


class TestDigemidResult:
    """Test DigemidResult model."""

    def test_default_values(self):
        data = DigemidResult()
        assert data.search_term == ""
        assert data.product_name == ""
        assert data.registration_number == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = DigemidResult(
            search_term="paracetamol",
            product_name="Paracetamol 500mg",
            registration_number="DIGEMID-PE-123456",
            status="Vigente",
        )
        json_str = data.model_dump_json()
        restored = DigemidResult.model_validate_json(json_str)
        assert restored.search_term == "paracetamol"
        assert restored.product_name == "Paracetamol 500mg"
        assert restored.status == "Vigente"

    def test_audit_excluded_from_json(self):
        data = DigemidResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestDigemidSourceMeta:
    """Test DigemidSource metadata."""

    def test_meta_name(self):
        source = DigemidSource()
        assert source.meta().name == "pe.digemid"

    def test_meta_country(self):
        source = DigemidSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = DigemidSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = DigemidSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = DigemidSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = DigemidSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test DigemidSource._parse_result parsing logic."""

    def test_parse_found_product(self):
        source = DigemidSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Paracetamol 500mg\n"
            "Registro: DIGEMID-PE-123456\n"
            "Estado: Vigente\n"
            "Producto autorizado\n"
        )
        result = source._parse_result(mock_page, "paracetamol")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = DigemidSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False
        assert result.status == "No encontrado"

    def test_query_requires_product_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = DigemidSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "pe.digemid" in str(e)
