"""Unit tests for Costa Rica Registro Inmobiliario property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cr.registro_inmobiliario import RegistroInmobiliarioResult
from openquery.sources.cr.registro_inmobiliario import RegistroInmobiliarioSource


class TestRegistroInmobiliarioResult:
    """Test RegistroInmobiliarioResult model."""

    def test_default_values(self):
        data = RegistroInmobiliarioResult()
        assert data.finca_number == ""
        assert data.owner == ""
        assert data.liens == ""
        assert data.property_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroInmobiliarioResult(
            finca_number="SJ-123456-000",
            owner="ANA RODRIGUEZ",
            liens="SIN GRAVAMENES",
            property_type="TERRENO",
        )
        json_str = data.model_dump_json()
        restored = RegistroInmobiliarioResult.model_validate_json(json_str)
        assert restored.finca_number == "SJ-123456-000"
        assert restored.owner == "ANA RODRIGUEZ"
        assert restored.liens == "SIN GRAVAMENES"
        assert restored.property_type == "TERRENO"

    def test_audit_excluded_from_json(self):
        data = RegistroInmobiliarioResult(finca_number="SJ-123456-000", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroInmobiliarioSourceMeta:
    """Test RegistroInmobiliarioSource metadata."""

    def test_meta_name(self):
        source = RegistroInmobiliarioSource()
        assert source.meta().name == "cr.registro_inmobiliario"

    def test_meta_country(self):
        source = RegistroInmobiliarioSource()
        assert source.meta().country == "CR"

    def test_meta_requires_browser(self):
        source = RegistroInmobiliarioSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = RegistroInmobiliarioSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = RegistroInmobiliarioSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroInmobiliarioSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = RegistroInmobiliarioSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = RegistroInmobiliarioSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RegistroInmobiliarioSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = RegistroInmobiliarioSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "ANA RODRIGUEZ"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "HIPOTECA BANCO NACIONAL"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "CASA DE HABITACION"
        mock_row1.query_selector_all.return_value = [cell0, cell1, cell2]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "SJ-123456-000")
        assert result.finca_number == "SJ-123456-000"
        assert result.owner == "ANA RODRIGUEZ"
        assert result.liens == "HIPOTECA BANCO NACIONAL"
        assert result.property_type == "CASA DE HABITACION"

    def test_parse_empty_page(self):
        source = RegistroInmobiliarioSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "SJ-999999-000")
        assert result.finca_number == "SJ-999999-000"
        assert result.owner == ""
