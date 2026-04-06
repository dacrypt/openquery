"""Unit tests for Mexico COFEPRIS health establishments source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.cofepris_establecimientos import CofeprisEstablecimientosResult
from openquery.sources.mx.cofepris_establecimientos import CofeprisEstablecimientosSource


class TestCofeprisEstablecimientosResult:
    """Test CofeprisEstablecimientosResult model."""

    def test_default_values(self):
        data = CofeprisEstablecimientosResult()
        assert data.search_term == ""
        assert data.establishment_name == ""
        assert data.permit_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CofeprisEstablecimientosResult(
            search_term="Farmacia San Juan",
            establishment_name="Farmacia San Juan SA",
            permit_status="Autorizado",
        )
        json_str = data.model_dump_json()
        restored = CofeprisEstablecimientosResult.model_validate_json(json_str)
        assert restored.search_term == "Farmacia San Juan"
        assert restored.permit_status == "Autorizado"

    def test_audit_excluded_from_json(self):
        data = CofeprisEstablecimientosResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCofeprisEstablecimientosSourceMeta:
    """Test CofeprisEstablecimientosSource metadata."""

    def test_meta_name(self):
        source = CofeprisEstablecimientosSource()
        assert source.meta().name == "mx.cofepris_establecimientos"

    def test_meta_country(self):
        source = CofeprisEstablecimientosSource()
        assert source.meta().country == "MX"

    def test_meta_requires_browser(self):
        source = CofeprisEstablecimientosSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = CofeprisEstablecimientosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CofeprisEstablecimientosSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CofeprisEstablecimientosSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test CofeprisEstablecimientosSource._parse_result parsing logic."""

    def test_parse_authorized(self):
        source = CofeprisEstablecimientosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Establecimiento: Farmacia San Juan SA\n"
            "Estado: Autorizado\n"
            "Permiso vigente activo\n"
        )
        result = source._parse_result(mock_page, "Farmacia San Juan")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = CofeprisEstablecimientosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False

    def test_query_requires_establishment_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = CofeprisEstablecimientosSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "mx.cofepris_establecimientos" in str(e)
