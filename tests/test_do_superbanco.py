"""Tests for do.superbanco — Dominican Republic Superintendent of Banks source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSuperbancoSourceMeta:
    def test_meta(self):
        from openquery.sources.do.superbanco import SuperbancoSource
        meta = SuperbancoSource().meta()
        assert meta.name == "do.superbanco"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.do.superbanco import SuperbancoSource
        src = SuperbancoSource()
        with pytest.raises(SourceError, match="entity_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSuperbancoModel:
    def test_model_defaults(self):
        from openquery.models.do.superbanco import SuperbancoResult
        r = SuperbancoResult(search_term="Banco Popular")
        assert r.search_term == "Banco Popular"
        assert r.entity_name == ""
        assert r.entity_type == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.do.superbanco import SuperbancoResult
        r = SuperbancoResult(search_term="test", entity_name="Banco Popular", entity_type="Banco", status="Supervisada")  # noqa: E501
        data = r.model_dump_json()
        r2 = SuperbancoResult.model_validate_json(data)
        assert r2.entity_name == "Banco Popular"

    def test_audit_excluded(self):
        from openquery.models.do.superbanco import SuperbancoResult
        r = SuperbancoResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
