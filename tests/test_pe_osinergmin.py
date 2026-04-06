"""Tests for pe.osinergmin — OSINERGMIN energy/mining supervisor source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestOsinergminSourceMeta:
    def test_meta(self):
        from openquery.sources.pe.osinergmin import OsinergminSource
        meta = OsinergminSource().meta()
        assert meta.name == "pe.osinergmin"
        assert meta.country == "PE"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.pe.osinergmin import OsinergminSource
        src = OsinergminSource()
        with pytest.raises(SourceError, match="company_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestOsinergminModel:
    def test_model_defaults(self):
        from openquery.models.pe.osinergmin import OsinergminResult
        r = OsinergminResult(search_term="Repsol")
        assert r.search_term == "Repsol"
        assert r.company_name == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.pe.osinergmin import OsinergminResult
        r = OsinergminResult(search_term="Repsol", company_name="Repsol Perú", status="Supervisada")
        data = r.model_dump_json()
        r2 = OsinergminResult.model_validate_json(data)
        assert r2.status == "Supervisada"

    def test_audit_excluded(self):
        from openquery.models.pe.osinergmin import OsinergminResult
        r = OsinergminResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
