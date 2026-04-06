"""Unit tests for Peru SUNARP property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.sunarp_propiedad import SunarpPropiedadResult
from openquery.sources.pe.sunarp_propiedad import SunarpPropiedadSource


class TestSunarpPropiedadResult:
    """Test SunarpPropiedadResult model."""

    def test_default_values(self):
        data = SunarpPropiedadResult()
        assert data.search_value == ""
        assert data.owner == ""
        assert data.property_type == ""
        assert data.liens == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SunarpPropiedadResult(
            search_value="P01001234567",
            owner="Ana Maria Torres",
            property_type="Predio Urbano",
            liens=["Hipoteca: Banco de Credito"],
        )
        json_str = data.model_dump_json()
        restored = SunarpPropiedadResult.model_validate_json(json_str)
        assert restored.search_value == "P01001234567"
        assert restored.owner == "Ana Maria Torres"
        assert len(restored.liens) == 1

    def test_audit_excluded_from_json(self):
        data = SunarpPropiedadResult(search_value="P01001234567", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSunarpPropiedadSourceMeta:
    """Test SunarpPropiedadSource metadata."""

    def test_meta_name(self):
        source = SunarpPropiedadSource()
        assert source.meta().name == "pe.sunarp_propiedad"

    def test_meta_country(self):
        source = SunarpPropiedadSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = SunarpPropiedadSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = SunarpPropiedadSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SunarpPropiedadSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SunarpPropiedadSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test SunarpPropiedadSource._parse_result parsing logic."""

    def test_parse_property_with_liens(self):
        source = SunarpPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Titular: Ana Maria Torres\n"
            "Tipo: Predio Urbano\n"
            "Hipoteca: Banco de Credito\n"
            "Carga registrada\n"
        )
        result = source._parse_result(mock_page, "P01001234567")
        assert result.search_value == "P01001234567"
        assert result.owner == "Ana Maria Torres"
        assert len(result.liens) > 0

    def test_parse_clean_property(self):
        source = SunarpPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Titular: Carlos Gomez\n"
            "Tipo: Predio Rural\n"
        )
        result = source._parse_result(mock_page, "P02009876543")
        assert result.liens == []

    def test_query_requires_property_code(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = SunarpPropiedadSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "pe.sunarp_propiedad" in str(e)
