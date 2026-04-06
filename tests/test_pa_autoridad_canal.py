"""Tests for pa.autoridad_canal — ACP Panama Canal Authority source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAutoridadCanalSourceMeta:
    def test_meta(self):
        from openquery.sources.pa.autoridad_canal import AutoridadCanalSource
        meta = AutoridadCanalSource().meta()
        assert meta.name == "pa.autoridad_canal"
        assert meta.country == "PA"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.pa.autoridad_canal import AutoridadCanalSource
        src = AutoridadCanalSource()
        with pytest.raises(SourceError, match="search_term"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestAutoridadCanalModel:
    def test_model_defaults(self):
        from openquery.models.pa.autoridad_canal import AutoridadCanalResult
        r = AutoridadCanalResult(search_term="buque")
        assert r.search_term == "buque"
        assert r.total_results == 0

    def test_model_roundtrip(self):
        from openquery.models.pa.autoridad_canal import AutoridadCanalResult
        r = AutoridadCanalResult(search_term="buque", total_results=5, details="Canal query")
        data = r.model_dump_json()
        r2 = AutoridadCanalResult.model_validate_json(data)
        assert r2.total_results == 5

    def test_audit_excluded(self):
        from openquery.models.pa.autoridad_canal import AutoridadCanalResult
        r = AutoridadCanalResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
