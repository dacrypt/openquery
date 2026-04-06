"""Unit tests for pr.multas source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pr.multas import MultasResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pr.multas import MultasSource


class TestMultasResult:
    """Test MultasResult model."""

    def test_default_values(self):
        data = MultasResult()
        assert data.search_value == ""
        assert data.total_fines == 0
        assert data.fines_amount == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = MultasResult(
            search_value="ABC123",
            total_fines=3,
            fines_amount="$450.00",
            details={"Tablilla": "ABC123"},
        )
        json_str = data.model_dump_json()
        restored = MultasResult.model_validate_json(json_str)
        assert restored.total_fines == 3
        assert restored.fines_amount == "$450.00"
        assert restored.details == {"Tablilla": "ABC123"}

    def test_audit_excluded_from_json(self):
        data = MultasResult(search_value="test", audit=object())
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestMultasSourceMeta:
    """Test MultasSource metadata."""

    def test_meta_name(self):
        source = MultasSource()
        meta = source.meta()
        assert meta.name == "pr.multas"

    def test_meta_country(self):
        source = MultasSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = MultasSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = MultasSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = MultasSource()
        meta = source.meta()
        assert DocumentType.PLATE in meta.supported_inputs

    def test_default_timeout(self):
        source = MultasSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = MultasSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_search_value_raises(self):
        src = MultasSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_plate_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.PLATE, document_number="ABC123")
        assert inp.document_number == "ABC123"

    def test_plate_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.PLATE,
            document_number="",
            extra={"plate": "ABC123"},
        )
        assert inp.extra.get("plate") == "ABC123"


class TestParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_value: str = "ABC123"):
        source = MultasSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return source._parse_result(mock_page, search_value)

    def test_parse_total_fines_amount(self):
        result = self._parse("Total Multas: $450.00\nTablella: ABC123\n")
        assert result.fines_amount == "$450.00"

    def test_parse_balance(self):
        result = self._parse("Balance: $225.00\nTablella: ABC123\n")
        assert result.fines_amount == "$225.00"

    def test_parse_amount_due(self):
        result = self._parse("Amount Due: $150.00\n")
        assert result.fines_amount == "$150.00"

    def test_parse_violation_count(self):
        result = self._parse(
            "Multa #1: Exceso de velocidad\n"
            "Multa #2: Luz roja\n"
            "Multa #3: Estacionamiento\n"
        )
        assert result.total_fines == 3

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_value == "ABC123"
        assert result.total_fines == 0
        assert result.fines_amount == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        result = self._parse("Tablilla: ABC123\nFecha: 2024-01-15\n")
        assert "Tablilla" in result.details
        assert result.details["Tablilla"] == "ABC123"

    def test_search_value_preserved(self):
        result = self._parse("", search_value="XYZ789")
        assert result.search_value == "XYZ789"
