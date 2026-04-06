"""Tests for sv.ssf — SSF banking supervisor source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSsfSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.ssf import SsfSource
        meta = SsfSource().meta()
        assert meta.name == "sv.ssf"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.sv.ssf import SsfSource
        src = SsfSource()
        with pytest.raises(SourceError, match="entity_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSsfModel:
    def test_model_defaults(self):
        from openquery.models.sv.ssf import SsfResult
        r = SsfResult(search_term="Banco Agrícola")
        assert r.search_term == "Banco Agrícola"
        assert r.entity_name == ""
        assert r.entity_type == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.sv.ssf import SsfResult
        r = SsfResult(search_term="test", entity_name="Banco Agrícola", entity_type="Banco", status="Supervisada")  # noqa: E501
        data = r.model_dump_json()
        r2 = SsfResult.model_validate_json(data)
        assert r2.entity_name == "Banco Agrícola"

    def test_audit_excluded(self):
        from openquery.models.sv.ssf import SsfResult
        r = SsfResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
