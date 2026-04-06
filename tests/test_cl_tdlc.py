"""Tests for cl.tdlc — TDLC antitrust tribunal source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestTdlcSourceMeta:
    def test_meta(self):
        from openquery.sources.cl.tdlc import TdlcSource
        meta = TdlcSource().meta()
        assert meta.name == "cl.tdlc"
        assert meta.country == "CL"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.cl.tdlc import TdlcSource
        src = TdlcSource()
        with pytest.raises(SourceError, match="case_number"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestTdlcModel:
    def test_model_defaults(self):
        from openquery.models.cl.tdlc import TdlcResult
        r = TdlcResult(search_term="Caso 123")
        assert r.search_term == "Caso 123"
        assert r.case_number == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.cl.tdlc import TdlcResult
        r = TdlcResult(search_term="Caso 123", case_number="FNE-123", status="Resuelto")
        data = r.model_dump_json()
        r2 = TdlcResult.model_validate_json(data)
        assert r2.status == "Resuelto"

    def test_audit_excluded(self):
        from openquery.models.cl.tdlc import TdlcResult
        r = TdlcResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
