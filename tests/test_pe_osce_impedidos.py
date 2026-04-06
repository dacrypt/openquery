"""Unit tests for Peru OSCE debarred contractors source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.osce_impedidos import OsceImpedidosResult
from openquery.sources.pe.osce_impedidos import OsceImpedidosSource


class TestOsceImpedidosResult:
    """Test OsceImpedidosResult model."""

    def test_default_values(self):
        data = OsceImpedidosResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.ruc == ""
        assert data.debarment_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OsceImpedidosResult(
            search_term="20123456789",
            company_name="Constructora XYZ SAC",
            ruc="20123456789",
            debarment_status="Impedido",
        )
        json_str = data.model_dump_json()
        restored = OsceImpedidosResult.model_validate_json(json_str)
        assert restored.ruc == "20123456789"
        assert restored.debarment_status == "Impedido"

    def test_audit_excluded_from_json(self):
        data = OsceImpedidosResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestOsceImpedidosSourceMeta:
    """Test OsceImpedidosSource metadata."""

    def test_meta_name(self):
        source = OsceImpedidosSource()
        assert source.meta().name == "pe.osce_impedidos"

    def test_meta_country(self):
        source = OsceImpedidosSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = OsceImpedidosSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = OsceImpedidosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = OsceImpedidosSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = OsceImpedidosSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test OsceImpedidosSource._parse_result parsing logic."""

    def test_parse_debarred(self):
        source = OsceImpedidosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Constructora XYZ SAC\n"
            "RUC: 20123456789\n"
            "Estado: Impedido inhabilitado\n"
        )
        result = source._parse_result(mock_page, "20123456789")
        assert result.details["is_debarred"] is True

    def test_parse_not_found(self):
        source = OsceImpedidosSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "00000000000")
        assert result.details["is_debarred"] is False

    def test_query_requires_search_term(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = OsceImpedidosSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "pe.osce_impedidos" in str(e)
