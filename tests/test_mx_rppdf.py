"""Unit tests for Mexico RPPDF CDMX property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.rppdf import RppdfResult
from openquery.sources.mx.rppdf import RppdfSource


class TestRppdfResult:
    """Test RppdfResult model."""

    def test_default_values(self):
        data = RppdfResult()
        assert data.folio == ""
        assert data.owner == ""
        assert data.property_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RppdfResult(
            folio="12345678",
            owner="Roberto Martinez",
            property_type="Casa Habitacion",
        )
        json_str = data.model_dump_json()
        restored = RppdfResult.model_validate_json(json_str)
        assert restored.folio == "12345678"
        assert restored.owner == "Roberto Martinez"

    def test_audit_excluded_from_json(self):
        data = RppdfResult(folio="12345678", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRppdfSourceMeta:
    """Test RppdfSource metadata."""

    def test_meta_name(self):
        source = RppdfSource()
        assert source.meta().name == "mx.rppdf"

    def test_meta_country(self):
        source = RppdfSource()
        assert source.meta().country == "MX"

    def test_meta_requires_browser(self):
        source = RppdfSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = RppdfSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RppdfSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RppdfSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RppdfSource._parse_result parsing logic."""

    def test_parse_property(self):
        source = RppdfSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Propietario: Roberto Martinez\n"
            "Tipo de Inmueble: Casa Habitacion\n"
        )
        result = source._parse_result(mock_page, "12345678")
        assert result.folio == "12345678"
        assert result.owner == "Roberto Martinez"

    def test_parse_empty(self):
        source = RppdfSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Consulta realizada."
        result = source._parse_result(mock_page, "00000000")
        assert result.folio == "00000000"
        assert result.owner == ""

    def test_query_requires_folio(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = RppdfSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "mx.rppdf" in str(e)
