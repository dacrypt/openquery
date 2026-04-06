"""Unit tests for pr.hacienda source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pr.hacienda import HaciendaResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pr.hacienda import HaciendaSource


class TestHaciendaResult:
    """Test HaciendaResult model."""

    def test_default_values(self):
        data = HaciendaResult()
        assert data.search_value == ""
        assert data.merchant_name == ""
        assert data.tax_status == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = HaciendaResult(
            search_value="123456",
            merchant_name="TIENDA EJEMPLO INC",
            tax_status="Al día",
            registration_status="Activo",
            details={"Número de Comerciante": "123456"},
        )
        json_str = data.model_dump_json()
        restored = HaciendaResult.model_validate_json(json_str)
        assert restored.merchant_name == "TIENDA EJEMPLO INC"
        assert restored.tax_status == "Al día"
        assert restored.registration_status == "Activo"
        assert restored.details == {"Número de Comerciante": "123456"}

    def test_audit_excluded_from_json(self):
        data = HaciendaResult(search_value="test", audit=object())
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestHaciendaSourceMeta:
    """Test HaciendaSource metadata."""

    def test_meta_name(self):
        source = HaciendaSource()
        meta = source.meta()
        assert meta.name == "pr.hacienda"

    def test_meta_country(self):
        source = HaciendaSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = HaciendaSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = HaciendaSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = HaciendaSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = HaciendaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = HaciendaSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_search_value_raises(self):
        src = HaciendaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_search_value_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="123456")
        assert inp.document_number == "123456"

    def test_search_value_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"merchant_number": "123456"},
        )
        assert inp.extra.get("merchant_number") == "123456"


class TestParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_value: str = "123456"):
        source = HaciendaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_value)

    def test_parse_merchant_name(self):
        result = self._parse("Nombre del Comerciante: TIENDA EJEMPLO INC\nEstado: Activo\n")
        assert result.merchant_name == "TIENDA EJEMPLO INC"

    def test_parse_tax_status(self):
        result = self._parse("Estado Contributivo: Al día\nNombre: TIENDA EJEMPLO\n")
        assert result.tax_status == "Al día"

    def test_parse_registration_status(self):
        result = self._parse("Estado de Registro: Activo\nNombre: TIENDA EJEMPLO\n")
        assert result.registration_status == "Activo"

    def test_parse_english_fields(self):
        result = self._parse(
            "Name: EXAMPLE STORE INC\n"
            "Tax Status: Current\n"
            "Registration Status: Active\n"
        )
        assert result.merchant_name == "EXAMPLE STORE INC"
        assert result.tax_status == "Current"
        assert result.registration_status == "Active"

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_value == "123456"
        assert result.merchant_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Número de Comerciante: 123456\nDirección: San Juan, PR\n")
        assert "Número de Comerciante" in result.details
        assert result.details["Número de Comerciante"] == "123456"

    def test_search_value_preserved(self):
        result = self._parse("", search_value="789012")
        assert result.search_value == "789012"
