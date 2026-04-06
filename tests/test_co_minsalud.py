"""Unit tests for Colombia MinSalud health provider registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.minsalud import MinsaludResult
from openquery.sources.co.minsalud import MinsaludSource


class TestMinsaludResult:
    """Test MinsaludResult model."""

    def test_default_values(self):
        data = MinsaludResult()
        assert data.search_term == ""
        assert data.provider_name == ""
        assert data.provider_type == ""
        assert data.habilitacion_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = MinsaludResult(
            search_term="Clinica Central",
            provider_name="Clinica Central SA",
            provider_type="IPS",
            habilitacion_status="Habilitado",
        )
        json_str = data.model_dump_json()
        restored = MinsaludResult.model_validate_json(json_str)
        assert restored.search_term == "Clinica Central"
        assert restored.provider_name == "Clinica Central SA"
        assert restored.habilitacion_status == "Habilitado"

    def test_audit_excluded_from_json(self):
        data = MinsaludResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestMinsaludSourceMeta:
    """Test MinsaludSource metadata."""

    def test_meta_name(self):
        source = MinsaludSource()
        assert source.meta().name == "co.minsalud"

    def test_meta_country(self):
        source = MinsaludSource()
        assert source.meta().country == "CO"

    def test_meta_requires_browser(self):
        source = MinsaludSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = MinsaludSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = MinsaludSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = MinsaludSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test MinsaludSource._parse_result parsing logic."""

    def test_parse_habilitado(self):
        source = MinsaludSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Clinica Central SA\n"
            "Tipo: IPS\n"
            "Habilitado: Si\n"
            "Prestador activo inscrito\n"
        )
        result = source._parse_result(mock_page, "Clinica Central")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = MinsaludSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "clinica_inexistente")
        assert result.details["found"] is False
        assert result.habilitacion_status == "No encontrado"

    def test_query_requires_provider_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = MinsaludSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "co.minsalud" in str(e)
