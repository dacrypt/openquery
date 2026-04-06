"""Unit tests for Colombia INVIMA health product registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.invima import InvimaResult
from openquery.sources.co.invima import InvimaSource


class TestInvimaResult:
    """Test InvimaResult model."""

    def test_default_values(self):
        data = InvimaResult()
        assert data.search_term == ""
        assert data.product_name == ""
        assert data.registration_number == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = InvimaResult(
            search_term="amoxicilina",
            product_name="Amoxicilina 500mg",
            registration_number="INVIMA2023M-123456",
            status="Vigente",
        )
        json_str = data.model_dump_json()
        restored = InvimaResult.model_validate_json(json_str)
        assert restored.search_term == "amoxicilina"
        assert restored.product_name == "Amoxicilina 500mg"
        assert restored.registration_number == "INVIMA2023M-123456"
        assert restored.status == "Vigente"

    def test_audit_excluded_from_json(self):
        data = InvimaResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestInvimaSourceMeta:
    """Test InvimaSource metadata."""

    def test_meta_name(self):
        source = InvimaSource()
        assert source.meta().name == "co.invima"

    def test_meta_country(self):
        source = InvimaSource()
        assert source.meta().country == "CO"

    def test_meta_requires_browser(self):
        source = InvimaSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = InvimaSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = InvimaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = InvimaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = InvimaSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = InvimaSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test InvimaSource._parse_result parsing logic."""

    def test_parse_found_product(self):
        source = InvimaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Resultado de Consulta\n"
            "Producto: Amoxicilina 500mg\n"
            "Expediente: INVIMA2023M-123456\n"
            "Estado: Vigente\n"
            "Registro Sanitario activo\n"
        )
        result = source._parse_result(mock_page, "amoxicilina")
        assert result.search_term == "amoxicilina"
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = InvimaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados para su busqueda."
        result = source._parse_result(mock_page, "producto_inexistente")
        assert result.details["found"] is False
        assert result.status == "No encontrado"

    def test_query_requires_product_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = InvimaSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "co.invima" in str(e)
