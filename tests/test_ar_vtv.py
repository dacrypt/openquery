"""Unit tests for Argentina VTV (Buenos Aires Province) vehicle inspection source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.vtv import VtvResult
from openquery.sources.ar.vtv import VtvSource


class TestVtvResult:
    """Test VtvResult model."""

    def test_default_values(self):
        data = VtvResult()
        assert data.placa == ""
        assert data.vtv_status == ""
        assert data.expiration_date == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = VtvResult(
            placa="ABC123",
            vtv_status="VIGENTE",
            expiration_date="30/06/2025",
            details={"raw_text": "VTV vigente"},
        )
        json_str = data.model_dump_json()
        restored = VtvResult.model_validate_json(json_str)
        assert restored.placa == "ABC123"
        assert restored.vtv_status == "VIGENTE"
        assert restored.expiration_date == "30/06/2025"

    def test_audit_excluded_from_json(self):
        data = VtvResult(placa="ABC123", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestVtvSourceMeta:
    """Test VtvSource metadata."""

    def test_meta_name(self):
        source = VtvSource()
        assert source.meta().name == "ar.vtv"

    def test_meta_country(self):
        source = VtvSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = VtvSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = VtvSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = VtvSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = VtvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = VtvSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = VtvSource()
        assert DocumentType.PLATE in source.meta().supported_inputs

    def test_query_wrong_document_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = VtvSource()
        with __import__("pytest").raises(SourceError, match="Unsupported document type"):
            source.query(QueryInput(document_type=DocumentType.CEDULA, document_number="123"))


class TestParseResult:
    """Test _parse_result parsing logic."""

    def test_parse_vigente_status(self):
        source = VtvSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "VTV VIGENTE - Vencimiento: 30/06/2025"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.placa == "ABC123"
        assert result.vtv_status == "VIGENTE"
        assert result.expiration_date == "30/06/2025"

    def test_parse_vencida_status(self):
        source = VtvSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "VTV VENCIDA para el dominio ABC123"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.vtv_status == "VENCIDA"

    def test_parse_sin_vtv_status(self):
        source = VtvSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No registra VTV para el dominio ingresado"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "XYZ999")
        assert result.vtv_status == "SIN VTV"

    def test_parse_table_expiration(self):
        source = VtvSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_label = MagicMock()
        mock_label.inner_text.return_value = "Vencimiento"
        mock_value = MagicMock()
        mock_value.inner_text.return_value = "31/12/2025"
        mock_row = MagicMock()
        mock_row.query_selector_all.return_value = [mock_label, mock_value]
        mock_page.query_selector_all.return_value = [mock_row]

        result = source._parse_result(mock_page, "ABC123")
        assert result.expiration_date == "31/12/2025"

    def test_parse_plate_uppercased(self):
        source = VtvSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "abc123")
        assert result.placa == "ABC123"
