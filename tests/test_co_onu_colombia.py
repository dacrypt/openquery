"""Unit tests for Colombia ONU sanctions source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.onu_colombia import OnuColombiaResult
from openquery.sources.co.onu_colombia import OnuColombiaSource


class TestOnuColombiaResult:
    """Test OnuColombiaResult model."""

    def test_default_values(self):
        data = OnuColombiaResult()
        assert data.search_term == ""
        assert data.is_sanctioned is False
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OnuColombiaResult(
            search_term="Test Person",
            is_sanctioned=True,
        )
        json_str = data.model_dump_json()
        restored = OnuColombiaResult.model_validate_json(json_str)
        assert restored.search_term == "Test Person"
        assert restored.is_sanctioned is True

    def test_audit_excluded_from_json(self):
        data = OnuColombiaResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestOnuColombiaSourceMeta:
    """Test OnuColombiaSource metadata."""

    def test_meta_name(self):
        source = OnuColombiaSource()
        assert source.meta().name == "co.onu_colombia"

    def test_meta_country(self):
        source = OnuColombiaSource()
        assert source.meta().country == "CO"

    def test_meta_requires_browser(self):
        source = OnuColombiaSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = OnuColombiaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = OnuColombiaSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = OnuColombiaSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test OnuColombiaSource._parse_result parsing logic."""

    def test_parse_sanctioned(self):
        source = OnuColombiaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Persona sancionada designada listado ONU"
        result = source._parse_result(mock_page, "Test Person")
        assert result.is_sanctioned is True

    def test_parse_not_sanctioned(self):
        source = OnuColombiaSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "John Doe")
        assert result.is_sanctioned is False

    def test_query_requires_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = OnuColombiaSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "co.onu_colombia" in str(e)
