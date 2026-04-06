"""Unit tests for Dominican Republic land titles registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.do.registro_titulos import RegistroTitulosResult
from openquery.sources.do.registro_titulos import RegistroTitulosSource


class TestRegistroTitulosResult:
    """Test RegistroTitulosResult model."""

    def test_default_values(self):
        data = RegistroTitulosResult()
        assert data.search_value == ""
        assert data.title_status == ""
        assert data.owner == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroTitulosResult(
            search_value="DO-PARCEL-001",
            title_status="Registrado",
            owner="Pedro Sanchez",
        )
        json_str = data.model_dump_json()
        restored = RegistroTitulosResult.model_validate_json(json_str)
        assert restored.search_value == "DO-PARCEL-001"
        assert restored.title_status == "Registrado"

    def test_audit_excluded_from_json(self):
        data = RegistroTitulosResult(search_value="DO-001", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroTitulosSourceMeta:
    """Test RegistroTitulosSource metadata."""

    def test_meta_name(self):
        source = RegistroTitulosSource()
        assert source.meta().name == "do.registro_titulos"

    def test_meta_country(self):
        source = RegistroTitulosSource()
        assert source.meta().country == "DO"

    def test_meta_requires_browser(self):
        source = RegistroTitulosSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = RegistroTitulosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroTitulosSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RegistroTitulosSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RegistroTitulosSource._parse_result parsing logic."""

    def test_parse_registered(self):
        source = RegistroTitulosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Titular: Pedro Sanchez\n"
            "Estado del Titulo: Vigente\n"
            "Registro activo\n"
        )
        result = source._parse_result(mock_page, "DO-PARCEL-001")
        assert result.owner == "Pedro Sanchez"
        assert result.title_status == "Vigente"

    def test_parse_not_found(self):
        source = RegistroTitulosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "DO-000")
        assert result.title_status == "No encontrado"

    def test_query_requires_parcel_number(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = RegistroTitulosSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "do.registro_titulos" in str(e)
