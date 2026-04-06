"""Unit tests for Paraguay property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.py.registro_propiedad import RegistroPropiedadPyResult
from openquery.sources.py.registro_propiedad import RegistroPropiedadPySource


class TestRegistroPropiedadPyResult:
    """Test RegistroPropiedadPyResult model."""

    def test_default_values(self):
        data = RegistroPropiedadPyResult()
        assert data.finca_number == ""
        assert data.owner == ""
        assert data.property_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroPropiedadPyResult(
            finca_number="12345-0",
            owner="Miguel Benitez",
            property_type="Inmueble Urbano",
        )
        json_str = data.model_dump_json()
        restored = RegistroPropiedadPyResult.model_validate_json(json_str)
        assert restored.finca_number == "12345-0"
        assert restored.owner == "Miguel Benitez"

    def test_audit_excluded_from_json(self):
        data = RegistroPropiedadPyResult(finca_number="12345-0", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroPropiedadPySourceMeta:
    """Test RegistroPropiedadPySource metadata."""

    def test_meta_name(self):
        source = RegistroPropiedadPySource()
        assert source.meta().name == "py.registro_propiedad"

    def test_meta_country(self):
        source = RegistroPropiedadPySource()
        assert source.meta().country == "PY"

    def test_meta_requires_browser(self):
        source = RegistroPropiedadPySource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = RegistroPropiedadPySource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroPropiedadPySource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RegistroPropiedadPySource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RegistroPropiedadPySource._parse_result parsing logic."""

    def test_parse_property(self):
        source = RegistroPropiedadPySource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Titular: Miguel Benitez\n"
            "Tipo de Inmueble: Urbano\n"
        )
        result = source._parse_result(mock_page, "12345-0")
        assert result.finca_number == "12345-0"
        assert result.owner == "Miguel Benitez"

    def test_parse_empty(self):
        source = RegistroPropiedadPySource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Consulta realizada."
        result = source._parse_result(mock_page, "00000-0")
        assert result.finca_number == "00000-0"
        assert result.owner == ""

    def test_query_requires_finca_number(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = RegistroPropiedadPySource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "py.registro_propiedad" in str(e)
