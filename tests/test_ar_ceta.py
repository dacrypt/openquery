"""Unit tests for Argentina CETA (DNRPA transfer certificate) source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.ceta import CetaResult
from openquery.sources.ar.ceta import CetaSource


class TestCetaResult:
    """Test CetaResult model."""

    def test_default_values(self):
        data = CetaResult()
        assert data.placa == ""
        assert data.ceta_status == ""
        assert data.issuance_date == ""
        assert data.expiration_date == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CetaResult(
            placa="ABC123",
            ceta_status="VIGENTE",
            issuance_date="01/01/2024",
            expiration_date="01/01/2025",
            details={"raw_text": "CETA vigente"},
        )
        json_str = data.model_dump_json()
        restored = CetaResult.model_validate_json(json_str)
        assert restored.placa == "ABC123"
        assert restored.ceta_status == "VIGENTE"
        assert restored.issuance_date == "01/01/2024"
        assert restored.expiration_date == "01/01/2025"

    def test_audit_excluded_from_json(self):
        data = CetaResult(placa="ABC123", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCetaSourceMeta:
    """Test CetaSource metadata."""

    def test_meta_name(self):
        source = CetaSource()
        assert source.meta().name == "ar.ceta"

    def test_meta_country(self):
        source = CetaSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = CetaSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CetaSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = CetaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CetaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CetaSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CetaSource()
        assert DocumentType.PLATE in source.meta().supported_inputs

    def test_query_wrong_document_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = CetaSource()
        with __import__("pytest").raises(SourceError, match="Unsupported document type"):
            source.query(QueryInput(document_type=DocumentType.CEDULA, document_number="123"))


class TestParseResult:
    """Test _parse_result parsing logic."""

    def test_parse_vigente_status(self):
        source = CetaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "CETA VIGENTE\nEmisión: 01/03/2024\nVencimiento: 01/03/2025"
        )
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.placa == "ABC123"
        assert result.ceta_status == "VIGENTE"
        assert result.issuance_date == "01/03/2024"
        assert result.expiration_date == "01/03/2025"

    def test_parse_vencido_status(self):
        source = CetaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "CETA VENCIDO para el dominio ABC123"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.ceta_status == "VENCIDO"

    def test_parse_sin_ceta_status(self):
        source = CetaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No registra CETA para el dominio ingresado"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "XYZ999")
        assert result.ceta_status == "SIN CETA"

    def test_parse_table_dates(self):
        source = CetaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_label_emit = MagicMock()
        mock_label_emit.inner_text.return_value = "Emisión"
        mock_value_emit = MagicMock()
        mock_value_emit.inner_text.return_value = "15/06/2024"
        mock_row_emit = MagicMock()
        mock_row_emit.query_selector_all.return_value = [mock_label_emit, mock_value_emit]

        mock_label_exp = MagicMock()
        mock_label_exp.inner_text.return_value = "Vencimiento"
        mock_value_exp = MagicMock()
        mock_value_exp.inner_text.return_value = "15/06/2025"
        mock_row_exp = MagicMock()
        mock_row_exp.query_selector_all.return_value = [mock_label_exp, mock_value_exp]

        mock_page.query_selector_all.return_value = [mock_row_emit, mock_row_exp]

        result = source._parse_result(mock_page, "ABC123")
        assert result.issuance_date == "15/06/2024"
        assert result.expiration_date == "15/06/2025"

    def test_parse_plate_uppercased(self):
        source = CetaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "abc123")
        assert result.placa == "ABC123"
