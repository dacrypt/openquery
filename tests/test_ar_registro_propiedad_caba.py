"""Unit tests for Argentina CABA property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.registro_propiedad_caba import RegistroPropiedadCabaResult
from openquery.sources.ar.registro_propiedad_caba import RegistroPropiedadCabaSource


class TestRegistroPropiedadCabaResult:
    """Test RegistroPropiedadCabaResult model."""

    def test_default_values(self):
        data = RegistroPropiedadCabaResult()
        assert data.search_value == ""
        assert data.owner == ""
        assert data.property_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroPropiedadCabaResult(
            search_value="CABA-12345",
            owner="Lucia Fernandez",
            property_type="Departamento",
        )
        json_str = data.model_dump_json()
        restored = RegistroPropiedadCabaResult.model_validate_json(json_str)
        assert restored.search_value == "CABA-12345"
        assert restored.owner == "Lucia Fernandez"

    def test_audit_excluded_from_json(self):
        data = RegistroPropiedadCabaResult(search_value="CABA-12345", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroPropiedadCabaSourceMeta:
    """Test RegistroPropiedadCabaSource metadata."""

    def test_meta_name(self):
        source = RegistroPropiedadCabaSource()
        assert source.meta().name == "ar.registro_propiedad_caba"

    def test_meta_country(self):
        source = RegistroPropiedadCabaSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = RegistroPropiedadCabaSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = RegistroPropiedadCabaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroPropiedadCabaSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RegistroPropiedadCabaSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RegistroPropiedadCabaSource._parse_result parsing logic."""

    def test_parse_property(self):
        source = RegistroPropiedadCabaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Titular: Lucia Fernandez\n"
            "Tipo de Inmueble: Departamento\n"
        )
        result = source._parse_result(mock_page, "CABA-12345")
        assert result.search_value == "CABA-12345"
        assert result.owner == "Lucia Fernandez"

    def test_parse_empty(self):
        source = RegistroPropiedadCabaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Consulta procesada."
        result = source._parse_result(mock_page, "CABA-00000")
        assert result.owner == ""

    def test_query_requires_property_number(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = RegistroPropiedadCabaSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "ar.registro_propiedad_caba" in str(e)
