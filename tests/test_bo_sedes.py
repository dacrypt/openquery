"""Unit tests for Bolivia SEDES health establishments source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.bo.sedes import SedesResult
from openquery.sources.bo.sedes import SedesSource


class TestSedesResult:
    """Test SedesResult model."""

    def test_default_values(self):
        data = SedesResult()
        assert data.search_term == ""
        assert data.establishment_name == ""
        assert data.permit_status == ""
        assert data.department == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SedesResult(
            search_term="Centro de Salud",
            establishment_name="Centro de Salud La Paz",
            permit_status="Autorizado",
            department="La Paz",
        )
        json_str = data.model_dump_json()
        restored = SedesResult.model_validate_json(json_str)
        assert restored.search_term == "Centro de Salud"
        assert restored.department == "La Paz"

    def test_audit_excluded_from_json(self):
        data = SedesResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSedesSourceMeta:
    """Test SedesSource metadata."""

    def test_meta_name(self):
        source = SedesSource()
        assert source.meta().name == "bo.sedes"

    def test_meta_country(self):
        source = SedesSource()
        assert source.meta().country == "BO"

    def test_meta_requires_browser(self):
        source = SedesSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = SedesSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SedesSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SedesSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test SedesSource._parse_result parsing logic."""

    def test_parse_authorized(self):
        source = SedesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Centro de Salud La Paz\n"
            "Departamento: La Paz\n"
            "Estado: Autorizado\n"
            "Permiso habilitado activo\n"
        )
        result = source._parse_result(mock_page, "Centro de Salud")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = SedesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False

    def test_query_requires_establishment_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = SedesSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "bo.sedes" in str(e)
