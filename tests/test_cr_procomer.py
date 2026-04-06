"""Tests for cr.procomer — Costa Rica PROCOMER export/trade data source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCrProcomerParseResult:
    def _parse(self, body_text: str, search_term: str = "cafe"):
        from openquery.sources.cr.procomer import CrProcomerSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = CrProcomerSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.total_results == 0

    def test_search_term_preserved(self):
        result = self._parse("", search_term="piña")
        assert result.search_term == "piña"

    def test_details_populated(self):
        result = self._parse("Exportaciones: Café 100 millones")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.cr.procomer import CrProcomerResult

        r = CrProcomerResult(
            search_term="cafe",
            total_results=5,
        )
        data = r.model_dump_json()
        r2 = CrProcomerResult.model_validate_json(data)
        assert r2.search_term == "cafe"
        assert r2.total_results == 5

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.procomer import CrProcomerResult

        r = CrProcomerResult(search_term="cafe", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestCrProcomerSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.procomer import CrProcomerSource

        meta = CrProcomerSource().meta()
        assert meta.name == "cr.procomer"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_term_raises(self):
        from openquery.sources.cr.procomer import CrProcomerSource

        src = CrProcomerSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
