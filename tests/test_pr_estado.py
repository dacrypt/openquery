"""Tests for pr.estado — Puerto Rico Department of State business filings source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPrEstadoParseResult:
    def _parse(self, body_text: str, search_term: str = "Test Corp"):
        from openquery.sources.pr.estado import PrEstadoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = PrEstadoSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.entity_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="ABC Corp")
        assert result.search_term == "ABC Corp"

    def test_parses_entity_name(self):
        body = "Entity Name: Test Corporation PR\nStatus: Active"
        result = self._parse(body)
        assert result.entity_name == "Test Corporation PR"

    def test_parses_status(self):
        body = "Status: Good Standing\nEntity Type: Corporation"
        result = self._parse(body)
        assert result.status == "Good Standing"

    def test_model_roundtrip(self):
        from openquery.models.pr.estado import PrEstadoResult

        r = PrEstadoResult(search_term="Test Corp", entity_name="Test Corp PR", status="Active")
        data = r.model_dump_json()
        r2 = PrEstadoResult.model_validate_json(data)
        assert r2.entity_name == "Test Corp PR"

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.estado import PrEstadoResult

        r = PrEstadoResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestPrEstadoSourceMeta:
    def test_meta(self):
        from openquery.sources.pr.estado import PrEstadoSource

        meta = PrEstadoSource().meta()
        assert meta.name == "pr.estado"
        assert meta.country == "PR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.pr.estado import PrEstadoSource

        src = PrEstadoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
