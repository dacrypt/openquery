"""Tests for gt.conred — Guatemala CONRED disaster/emergency events source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtConredParseResult:
    def _parse(self, body_text: str, search_term: str = "terremoto"):
        from openquery.sources.gt.conred import GtConredSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = GtConredSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.total_events == 0
        assert result.events == []

    def test_search_term_preserved(self):
        result = self._parse("", search_term="inundacion")
        assert result.search_term == "inundacion"

    def test_no_events_zero_total(self):
        result = self._parse("Sin resultados")
        assert result.total_events == 0

    def test_details_populated(self):
        result = self._parse("Emergencia: Terremoto Zona 3")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.gt.conred import GtConredResult

        r = GtConredResult(
            search_term="terremoto",
            total_events=3,
            events=[{"title": "Sismo 5.0", "date": "2024-01-01"}],
        )
        data = r.model_dump_json()
        r2 = GtConredResult.model_validate_json(data)
        assert r2.search_term == "terremoto"
        assert r2.total_events == 3
        assert len(r2.events) == 1

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.conred import GtConredResult

        r = GtConredResult(search_term="terremoto", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtConredSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.conred import GtConredSource

        meta = GtConredSource().meta()
        assert meta.name == "gt.conred"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_term_raises(self):
        from openquery.sources.gt.conred import GtConredSource

        src = GtConredSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
