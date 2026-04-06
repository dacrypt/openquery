"""Unit tests for Chile UAF financial intelligence source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.uaf import UafResult
from openquery.sources.cl.uaf import UafSource


class TestUafResult:
    """Test UafResult model."""

    def test_default_values(self):
        data = UafResult()
        assert data.search_term == ""
        assert data.is_designated is False
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = UafResult(
            search_term="Persona Designada",
            is_designated=True,
        )
        json_str = data.model_dump_json()
        restored = UafResult.model_validate_json(json_str)
        assert restored.search_term == "Persona Designada"
        assert restored.is_designated is True

    def test_audit_excluded_from_json(self):
        data = UafResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_not_designated_default(self):
        data = UafResult(search_term="Maria Gonzalez")
        assert data.is_designated is False


class TestUafSourceMeta:
    """Test UafSource metadata."""

    def test_meta_name(self):
        source = UafSource()
        assert source.meta().name == "cl.uaf"

    def test_meta_country(self):
        source = UafSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = UafSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = UafSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = UafSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = UafSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test UafSource._parse_result parsing logic."""

    def test_parse_designated(self):
        source = UafSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Persona designada listada encontrado UAF"
        result = source._parse_result(mock_page, "Persona Designada")
        assert result.is_designated is True

    def test_parse_not_designated(self):
        source = UafSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "Maria Gonzalez")
        assert result.is_designated is False

    def test_query_requires_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = UafSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "cl.uaf" in str(e)
