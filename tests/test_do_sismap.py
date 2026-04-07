"""Tests for do.sismap — Dominican Republic SISMAP government transparency source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSismapParseResult:
    def _parse(self, body_text: str, search_term: str = "Ministerio Test"):
        from openquery.sources.do.sismap import SismapSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SismapSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.performance_score == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="MIREX")
        assert result.search_term == "MIREX"

    def test_parses_entity_name(self):
        body = "Institución: Ministerio de Relaciones Exteriores\nPuntuación: 85"
        result = self._parse(body)
        assert result.entity_name == "Ministerio de Relaciones Exteriores"

    def test_parses_performance_score(self):
        body = "Puntuación: 92.5\nPeríodo: 2024"
        result = self._parse(body)
        assert result.performance_score == "92.5"

    def test_model_roundtrip(self):
        from openquery.models.do.sismap import SismapResult

        r = SismapResult(search_term="MIREX", entity_name="MIREX DO", performance_score="85")
        data = r.model_dump_json()
        r2 = SismapResult.model_validate_json(data)
        assert r2.performance_score == "85"

    def test_audit_excluded_from_json(self):
        from openquery.models.do.sismap import SismapResult

        r = SismapResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSismapSourceMeta:
    def test_meta(self):
        from openquery.sources.do.sismap import SismapSource

        meta = SismapSource().meta()
        assert meta.name == "do.sismap"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.do.sismap import SismapSource

        src = SismapSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
