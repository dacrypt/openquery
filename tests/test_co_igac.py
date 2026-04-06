"""Unit tests for Colombia IGAC catastro/property source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.igac import IgacResult
from openquery.sources.co.igac import IgacSource


class TestIgacResult:
    """Test IgacResult model."""

    def test_default_values(self):
        data = IgacResult()
        assert data.cadastral_code == ""
        assert data.owner == ""
        assert data.area == ""
        assert data.land_use == ""
        assert data.valuation == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IgacResult(
            cadastral_code="25001000100000001",
            owner="Juan Carlos Perez",
            area="500 m2",
            land_use="Residencial",
            valuation="$200,000,000",
        )
        json_str = data.model_dump_json()
        restored = IgacResult.model_validate_json(json_str)
        assert restored.cadastral_code == "25001000100000001"
        assert restored.owner == "Juan Carlos Perez"
        assert restored.land_use == "Residencial"

    def test_audit_excluded_from_json(self):
        data = IgacResult(cadastral_code="25001000100000001", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestIgacSourceMeta:
    """Test IgacSource metadata."""

    def test_meta_name(self):
        source = IgacSource()
        assert source.meta().name == "co.igac"

    def test_meta_country(self):
        source = IgacSource()
        assert source.meta().country == "CO"

    def test_meta_requires_browser(self):
        source = IgacSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = IgacSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = IgacSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = IgacSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test IgacSource._parse_result parsing logic."""

    def test_parse_property(self):
        source = IgacSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Propietario: Juan Carlos Perez\n"
            "Area: 500 m2\n"
            "Uso: Residencial\n"
            "Avaluo: $200,000,000\n"
        )
        result = source._parse_result(mock_page, "25001000100000001")
        assert result.cadastral_code == "25001000100000001"
        assert result.owner == "Juan Carlos Perez"

    def test_parse_empty(self):
        source = IgacSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Consulta realizada."
        result = source._parse_result(mock_page, "00000000000000000")
        assert result.cadastral_code == "00000000000000000"
        assert result.owner == ""

    def test_query_requires_cadastral_code(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = IgacSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "co.igac" in str(e)
