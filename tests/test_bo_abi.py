"""Tests for bo.abi — Bolivia ABI news agency source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestBoAbiParseResult:
    def _parse(self, body_text: str, search_term: str = "gobierno"):
        from openquery.sources.bo.abi import BoAbiSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = BoAbiSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.total_results == 0
        assert result.articles == []

    def test_search_term_preserved(self):
        result = self._parse("", search_term="economia")
        assert result.search_term == "economia"

    def test_no_articles_zero_total(self):
        result = self._parse("Sin resultados")
        assert result.total_results == 0

    def test_details_populated(self):
        result = self._parse("Noticias: Bolivia\nEconomía crece 3%")
        assert "raw" in result.details

    def test_model_roundtrip(self):
        from openquery.models.bo.abi import BoAbiResult

        r = BoAbiResult(
            search_term="gobierno",
            total_results=2,
            articles=[{"title": "Noticia 1", "date": "2024-01-01"}],
        )
        data = r.model_dump_json()
        r2 = BoAbiResult.model_validate_json(data)
        assert r2.search_term == "gobierno"
        assert r2.total_results == 2
        assert len(r2.articles) == 1

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.abi import BoAbiResult

        r = BoAbiResult(search_term="gobierno", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestBoAbiSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.abi import BoAbiSource

        meta = BoAbiSource().meta()
        assert meta.name == "bo.abi"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_term_raises(self):
        from openquery.sources.bo.abi import BoAbiSource

        src = BoAbiSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
