"""Tests for co.colciencias — MinCiencias research groups source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestColcienciasParseResult:
    def _make_source(self):
        from openquery.sources.co.colciencias import ColcienciasSource
        return ColcienciasSource()

    def test_meta(self):
        src = self._make_source()
        meta = src.meta()
        assert meta.name == "co.colciencias"
        assert meta.country == "CO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        src = self._make_source()
        with pytest.raises(SourceError, match="name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_search_term_from_document_number(self):
        self._make_source()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Rodriguez")
        assert inp.document_number == "Rodriguez"


class TestColcienciasModel:
    def test_model_defaults(self):
        from openquery.models.co.colciencias import ColcienciasResult
        r = ColcienciasResult(search_term="Rodriguez")
        assert r.search_term == "Rodriguez"
        assert r.researcher_name == ""
        assert r.group == ""
        assert r.category == ""

    def test_model_roundtrip(self):
        from openquery.models.co.colciencias import ColcienciasResult
        r = ColcienciasResult(search_term="Rodriguez", group="Grupo A", category="A1")
        data = r.model_dump_json()
        r2 = ColcienciasResult.model_validate_json(data)
        assert r2.search_term == "Rodriguez"
        assert r2.category == "A1"

    def test_audit_excluded(self):
        from openquery.models.co.colciencias import ColcienciasResult
        r = ColcienciasResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
