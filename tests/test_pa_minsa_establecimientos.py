"""Unit tests for Panama MINSA health providers source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pa.minsa_establecimientos import MinsaEstablecimientosResult
from openquery.sources.pa.minsa_establecimientos import MinsaEstablecimientosSource


class TestMinsaEstablecimientosResult:
    """Test MinsaEstablecimientosResult model."""

    def test_default_values(self):
        data = MinsaEstablecimientosResult()
        assert data.search_term == ""
        assert data.provider_name == ""
        assert data.license_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = MinsaEstablecimientosResult(
            search_term="Clinica Panama",
            provider_name="Clinica Panama SA",
            license_status="Licenciado",
        )
        json_str = data.model_dump_json()
        restored = MinsaEstablecimientosResult.model_validate_json(json_str)
        assert restored.search_term == "Clinica Panama"
        assert restored.license_status == "Licenciado"

    def test_audit_excluded_from_json(self):
        data = MinsaEstablecimientosResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestMinsaEstablecimientosSourceMeta:
    """Test MinsaEstablecimientosSource metadata."""

    def test_meta_name(self):
        source = MinsaEstablecimientosSource()
        assert source.meta().name == "pa.minsa_establecimientos"

    def test_meta_country(self):
        source = MinsaEstablecimientosSource()
        assert source.meta().country == "PA"

    def test_meta_requires_browser(self):
        source = MinsaEstablecimientosSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = MinsaEstablecimientosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = MinsaEstablecimientosSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = MinsaEstablecimientosSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test MinsaEstablecimientosSource._parse_result parsing logic."""

    def test_parse_licensed(self):
        source = MinsaEstablecimientosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Clinica Panama SA\n"
            "Licencia: Activa\n"
            "Proveedor autorizado habilitado\n"
        )
        result = source._parse_result(mock_page, "Clinica Panama")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = MinsaEstablecimientosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False

    def test_query_requires_provider_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = MinsaEstablecimientosSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "pa.minsa_establecimientos" in str(e)
