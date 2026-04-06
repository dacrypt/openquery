"""Unit tests for Ecuador ARCSA health establishments source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.arcsa_establecimientos import ArcsaEstablecimientosResult
from openquery.sources.ec.arcsa_establecimientos import ArcsaEstablecimientosSource


class TestArcsaEstablecimientosResult:
    """Test ArcsaEstablecimientosResult model."""

    def test_default_values(self):
        data = ArcsaEstablecimientosResult()
        assert data.search_term == ""
        assert data.establishment_name == ""
        assert data.permit_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ArcsaEstablecimientosResult(
            search_term="Laboratorio Quito",
            establishment_name="Laboratorio Quito SA",
            permit_status="Autorizado",
        )
        json_str = data.model_dump_json()
        restored = ArcsaEstablecimientosResult.model_validate_json(json_str)
        assert restored.search_term == "Laboratorio Quito"
        assert restored.permit_status == "Autorizado"

    def test_audit_excluded_from_json(self):
        data = ArcsaEstablecimientosResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestArcsaEstablecimientosSourceMeta:
    """Test ArcsaEstablecimientosSource metadata."""

    def test_meta_name(self):
        source = ArcsaEstablecimientosSource()
        assert source.meta().name == "ec.arcsa_establecimientos"

    def test_meta_country(self):
        source = ArcsaEstablecimientosSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = ArcsaEstablecimientosSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = ArcsaEstablecimientosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ArcsaEstablecimientosSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = ArcsaEstablecimientosSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test ArcsaEstablecimientosSource._parse_result parsing logic."""

    def test_parse_authorized(self):
        source = ArcsaEstablecimientosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Laboratorio Quito SA\n"
            "Estado: Autorizado\n"
            "Permiso vigente habilitado\n"
        )
        result = source._parse_result(mock_page, "Laboratorio Quito")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = ArcsaEstablecimientosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False

    def test_query_requires_establishment_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = ArcsaEstablecimientosSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "ec.arcsa_establecimientos" in str(e)
