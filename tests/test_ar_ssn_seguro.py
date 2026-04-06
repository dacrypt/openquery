"""Unit tests for Argentina SSN mandatory vehicle insurance source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.ssn_seguro import SsnSeguroResult
from openquery.sources.ar.ssn_seguro import SsnSeguroSource


class TestSsnSeguroResult:
    """Test SsnSeguroResult model."""

    def test_default_values(self):
        data = SsnSeguroResult()
        assert data.placa == ""
        assert data.has_insurance is False
        assert data.insurer == ""
        assert data.policy_valid is False
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SsnSeguroResult(
            placa="ABC123",
            has_insurance=True,
            insurer="La Caja",
            policy_valid=True,
            details={"raw_text": "Asegurado"},
        )
        json_str = data.model_dump_json()
        restored = SsnSeguroResult.model_validate_json(json_str)
        assert restored.placa == "ABC123"
        assert restored.has_insurance is True
        assert restored.insurer == "La Caja"
        assert restored.policy_valid is True

    def test_audit_excluded_from_json(self):
        data = SsnSeguroResult(placa="ABC123", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSsnSeguroSourceMeta:
    """Test SsnSeguroSource metadata."""

    def test_meta_name(self):
        source = SsnSeguroSource()
        assert source.meta().name == "ar.ssn_seguro"

    def test_meta_country(self):
        source = SsnSeguroSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = SsnSeguroSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SsnSeguroSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SsnSeguroSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SsnSeguroSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SsnSeguroSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SsnSeguroSource()
        assert DocumentType.PLATE in source.meta().supported_inputs

    def test_query_wrong_document_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = SsnSeguroSource()
        with __import__("pytest").raises(SourceError, match="Unsupported document type"):
            source.query(QueryInput(document_type=DocumentType.CEDULA, document_number="123"))


class TestParseResult:
    """Test _parse_result parsing logic."""

    def test_parse_has_insurance(self):
        source = SsnSeguroSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "El vehículo tiene seguro vigente. Cobertura vigente."
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.placa == "ABC123"
        assert result.has_insurance is True

    def test_parse_no_insurance(self):
        source = SsnSeguroSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "El vehículo no tiene seguro obligatorio"
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ABC123")
        assert result.has_insurance is False

    def test_parse_table_insurer(self):
        source = SsnSeguroSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "asegurado"

        mock_label = MagicMock()
        mock_label.inner_text.return_value = "Aseguradora"
        mock_value = MagicMock()
        mock_value.inner_text.return_value = "Federacion Patronal"
        mock_row = MagicMock()
        mock_row.query_selector_all.return_value = [mock_label, mock_value]
        mock_page.query_selector_all.return_value = [mock_row]

        result = source._parse_result(mock_page, "ABC123")
        assert result.insurer == "Federacion Patronal"
        assert result.has_insurance is True

    def test_parse_plate_uppercased(self):
        source = SsnSeguroSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "abc123")
        assert result.placa == "ABC123"
