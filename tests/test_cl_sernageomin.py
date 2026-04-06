"""Tests for cl.sernageomin — SERNAGEOMIN mining concessions source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSernageominSourceMeta:
    def test_meta(self):
        from openquery.sources.cl.sernageomin import SernageominSource
        meta = SernageominSource().meta()
        assert meta.name == "cl.sernageomin"
        assert meta.country == "CL"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.cl.sernageomin import SernageominSource
        src = SernageominSource()
        with pytest.raises(SourceError, match="concession_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSernageominModel:
    def test_model_defaults(self):
        from openquery.models.cl.sernageomin import SernageominResult
        r = SernageominResult(search_term="Mina Atacama")
        assert r.search_term == "Mina Atacama"
        assert r.concession_name == ""
        assert r.holder == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.cl.sernageomin import SernageominResult
        r = SernageominResult(search_term="test", concession_name="Mina X", holder="Codelco", status="Vigente")  # noqa: E501
        data = r.model_dump_json()
        r2 = SernageominResult.model_validate_json(data)
        assert r2.holder == "Codelco"

    def test_audit_excluded(self):
        from openquery.models.cl.sernageomin import SernageominResult
        r = SernageominResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
