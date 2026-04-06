"""Tests for mx.conagua — CONAGUA water concessions source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestConaguaSourceMeta:
    def test_meta(self):
        from openquery.sources.mx.conagua import ConaguaSource
        meta = ConaguaSource().meta()
        assert meta.name == "mx.conagua"
        assert meta.country == "MX"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.mx.conagua import ConaguaSource
        src = ConaguaSource()
        with pytest.raises(SourceError, match="concession_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestConaguaModel:
    def test_model_defaults(self):
        from openquery.models.mx.conagua import ConaguaResult
        r = ConaguaResult(search_term="Acueducto Norte")
        assert r.search_term == "Acueducto Norte"
        assert r.concession_name == ""
        assert r.holder == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.mx.conagua import ConaguaResult
        r = ConaguaResult(search_term="test", concession_name="AC-001", holder="Empresa Agua", status="Vigente")  # noqa: E501
        data = r.model_dump_json()
        r2 = ConaguaResult.model_validate_json(data)
        assert r2.holder == "Empresa Agua"

    def test_audit_excluded(self):
        from openquery.models.mx.conagua import ConaguaResult
        r = ConaguaResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
