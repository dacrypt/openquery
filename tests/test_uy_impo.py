"""Unit tests for uy.impo source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.uy.impo import UyImpoNorm, UyImpoResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.uy.impo import UyImpoSource


class TestUyImpoResult:
    """Test UyImpoResult model."""

    def test_default_values(self):
        data = UyImpoResult()
        assert data.search_term == ""
        assert data.total_results == 0
        assert data.norms == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = UyImpoResult(
            search_term="ley laboral",
            total_results=1,
            norms=[UyImpoNorm(title="Ley 18566", number="18566", date="2009-09-11")],
        )
        json_str = data.model_dump_json()
        restored = UyImpoResult.model_validate_json(json_str)
        assert restored.search_term == "ley laboral"
        assert restored.total_results == 1
        assert len(restored.norms) == 1
        assert restored.norms[0].title == "Ley 18566"

    def test_audit_excluded_from_json(self):
        data = UyImpoResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestUyImpoNorm:
    """Test UyImpoNorm model."""

    def test_default_values(self):
        n = UyImpoNorm()
        assert n.title == ""
        assert n.number == ""
        assert n.date == ""
        assert n.url == ""


class TestUyImpoSourceMeta:
    """Test UyImpoSource metadata."""

    def test_meta_name(self):
        source = UyImpoSource()
        meta = source.meta()
        assert meta.name == "uy.impo"

    def test_meta_country(self):
        source = UyImpoSource()
        meta = source.meta()
        assert meta.country == "UY"

    def test_meta_rate_limit(self):
        source = UyImpoSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = UyImpoSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = UyImpoSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = UyImpoSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = UyImpoSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_search_term_raises(self):
        src = UyImpoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_search_term_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="ley laboral")
        assert inp.document_number == "ley laboral"


class TestUyImpoParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "ley laboral", items=None):
        source = UyImpoSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if items is None:
            mock_page.query_selector_all.return_value = []
        else:
            mock_page.query_selector_all.return_value = items
        return source._parse_result(mock_page, search_term)

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "ley laboral"
        assert result.total_results == 0
        assert result.norms == []

    def test_parse_norm_items(self):
        mock_item = MagicMock()
        mock_item.inner_text.return_value = "Ley 18566 - Negociación Colectiva"
        mock_link = MagicMock()
        mock_link.inner_text.return_value = "Ley 18566"
        mock_link.get_attribute.return_value = "/bases/leyes/18566"
        mock_item.query_selector.return_value = mock_link
        result = self._parse("", items=[mock_item])
        assert len(result.norms) == 1
        assert result.norms[0].title == "Ley 18566"
        assert "impo.com.uy" in result.norms[0].url
        assert result.total_results == 1

    def test_search_term_preserved(self):
        result = self._parse("", search_term="decreto tributario")
        assert result.search_term == "decreto tributario"

    def test_model_roundtrip(self):
        r = UyImpoResult(search_term="ley laboral", total_results=5)
        data = r.model_dump_json()
        r2 = UyImpoResult.model_validate_json(data)
        assert r2.search_term == "ley laboral"
        assert r2.total_results == 5
