"""Unit tests for Mexico SAT 69-B Completo EFOS source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.sat_69b_completo import Sat69bCompletoResult
from openquery.sources.mx.sat_69b_completo import Sat69bCompletoSource


class TestSat69bCompletoResult:
    """Test Sat69bCompletoResult model."""

    def test_default_values(self):
        data = Sat69bCompletoResult()
        assert data.rfc == ""
        assert data.taxpayer_name == ""
        assert data.efos_status == ""
        assert data.classification == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = Sat69bCompletoResult(
            rfc="XAXX010101000",
            taxpayer_name="Empresa Fantasma SA",
            efos_status="Definitivo",
            classification="EFOS",
        )
        json_str = data.model_dump_json()
        restored = Sat69bCompletoResult.model_validate_json(json_str)
        assert restored.rfc == "XAXX010101000"
        assert restored.efos_status == "Definitivo"
        assert restored.classification == "EFOS"

    def test_audit_excluded_from_json(self):
        data = Sat69bCompletoResult(rfc="XAXX010101000", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSat69bCompletoSourceMeta:
    """Test Sat69bCompletoSource metadata."""

    def test_meta_name(self):
        source = Sat69bCompletoSource()
        assert source.meta().name == "mx.sat_69b_completo"

    def test_meta_country(self):
        source = Sat69bCompletoSource()
        assert source.meta().country == "MX"

    def test_meta_requires_browser(self):
        source = Sat69bCompletoSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = Sat69bCompletoSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = Sat69bCompletoSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = Sat69bCompletoSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test Sat69bCompletoSource._parse_result parsing logic."""

    def test_parse_efos_listed(self):
        source = Sat69bCompletoSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Empresa Fantasma SA\n"
            "Situacion: Definitiva EFOS presunta\n"
            "Clasificacion: EFOS\n"
        )
        result = source._parse_result(mock_page, "XAXX010101000")
        assert result.details["is_efos"] is True

    def test_parse_not_found(self):
        source = Sat69bCompletoSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "AAAA010101AAA")
        assert result.details["is_efos"] is False
        assert result.efos_status == "No encontrado"

    def test_query_requires_rfc(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = Sat69bCompletoSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "mx.sat_69b_completo" in str(e)
