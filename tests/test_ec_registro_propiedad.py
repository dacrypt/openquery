"""Unit tests for Ecuador property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.registro_propiedad import RegistroPropiedadResult
from openquery.sources.ec.registro_propiedad import RegistroPropiedadSource


class TestRegistroPropiedadResult:
    """Test RegistroPropiedadResult model."""

    def test_default_values(self):
        data = RegistroPropiedadResult()
        assert data.search_value == ""
        assert data.owner == ""
        assert data.property_type == ""
        assert data.liens == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroPropiedadResult(
            search_value="EC-PROP-001",
            owner="Sofia Castro",
            property_type="Lote Urbano",
            liens=["Hipoteca: Banco Pichincha"],
        )
        json_str = data.model_dump_json()
        restored = RegistroPropiedadResult.model_validate_json(json_str)
        assert restored.search_value == "EC-PROP-001"
        assert len(restored.liens) == 1

    def test_audit_excluded_from_json(self):
        data = RegistroPropiedadResult(search_value="EC-001", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroPropiedadSourceMeta:
    """Test RegistroPropiedadSource metadata."""

    def test_meta_name(self):
        source = RegistroPropiedadSource()
        assert source.meta().name == "ec.registro_propiedad"

    def test_meta_country(self):
        source = RegistroPropiedadSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = RegistroPropiedadSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = RegistroPropiedadSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroPropiedadSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RegistroPropiedadSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RegistroPropiedadSource._parse_result parsing logic."""

    def test_parse_property_with_liens(self):
        source = RegistroPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Titular: Sofia Castro\n"
            "Tipo: Lote Urbano\n"
            "Hipoteca: Banco Pichincha\n"
        )
        result = source._parse_result(mock_page, "EC-PROP-001")
        assert result.owner == "Sofia Castro"
        assert len(result.liens) > 0

    def test_parse_no_liens(self):
        source = RegistroPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Propietario: Carlos Vera\n"
            "Tipo: Casa\n"
        )
        result = source._parse_result(mock_page, "EC-PROP-002")
        assert result.liens == []

    def test_query_requires_property_code(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = RegistroPropiedadSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "ec.registro_propiedad" in str(e)
