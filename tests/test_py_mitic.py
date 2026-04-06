"""Tests for py.mitic — Paraguay MITIC open data portal source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPyMiticResult:
    def test_default_values(self):
        from openquery.models.py.mitic import PyMiticResult

        r = PyMiticResult()
        assert r.query == ""
        assert r.total_results == 0
        assert r.datasets == []
        assert r.details == {}
        assert r.audit is None

    def test_round_trip_json(self):
        from openquery.models.py.mitic import PyMiticDataset, PyMiticResult

        r = PyMiticResult(
            query="educacion",
            total_results=5,
            datasets=[PyMiticDataset(id="abc", title="Dataset Educacion", name="educacion")],
        )
        data = r.model_dump_json()
        r2 = PyMiticResult.model_validate_json(data)
        assert r2.query == "educacion"
        assert r2.total_results == 5
        assert len(r2.datasets) == 1
        assert r2.datasets[0].title == "Dataset Educacion"

    def test_audit_excluded_from_json(self):
        from openquery.models.py.mitic import PyMiticResult

        r = PyMiticResult(query="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestPyMiticSourceMeta:
    def test_meta(self):
        from openquery.sources.py.mitic import PyMiticSource

        meta = PyMiticSource().meta()
        assert meta.name == "py.mitic"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_empty_query_raises(self):
        from openquery.sources.py.mitic import PyMiticSource

        src = PyMiticSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_query(self):
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="educacion")
        assert qi.document_number == "educacion"

    def test_extra_query_param(self):
        qi = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"query": "salud"},
        )
        assert qi.extra["query"] == "salud"
