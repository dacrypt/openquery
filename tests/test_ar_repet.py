"""Unit tests for Argentina REPET terrorism financing registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.repet import RepetResult
from openquery.sources.ar.repet import RepetSource


class TestRepetResult:
    """Test RepetResult model."""

    def test_default_values(self):
        data = RepetResult()
        assert data.search_term == ""
        assert data.is_listed is False
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RepetResult(
            search_term="Persona Sospechosa",
            is_listed=True,
        )
        json_str = data.model_dump_json()
        restored = RepetResult.model_validate_json(json_str)
        assert restored.search_term == "Persona Sospechosa"
        assert restored.is_listed is True

    def test_audit_excluded_from_json(self):
        data = RepetResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_not_listed_default(self):
        data = RepetResult(search_term="Juan Perez")
        assert data.is_listed is False


class TestRepetSourceMeta:
    """Test RepetSource metadata."""

    def test_meta_name(self):
        source = RepetSource()
        assert source.meta().name == "ar.repet"

    def test_meta_country(self):
        source = RepetSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = RepetSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = RepetSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RepetSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RepetSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RepetSource._parse_result parsing logic."""

    def test_parse_listed(self):
        source = RepetSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Persona listada designada terrorismo encontrado"
        result = source._parse_result(mock_page, "Persona Sospechosa")
        assert result.is_listed is True

    def test_parse_not_listed(self):
        source = RepetSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "Juan Perez")
        assert result.is_listed is False

    def test_query_requires_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = RepetSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "ar.repet" in str(e)
