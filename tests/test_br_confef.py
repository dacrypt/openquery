"""Tests for br.confef — CONFEF physical education professional source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestConfefSourceMeta:
    def test_meta(self):
        from openquery.sources.br.confef import ConfefSource
        meta = ConfefSource().meta()
        assert meta.name == "br.confef"
        assert meta.country == "BR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_cref_raises(self):
        from openquery.sources.br.confef import ConfefSource
        src = ConfefSource()
        with pytest.raises(SourceError, match="CREF"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestConfefModel:
    def test_model_defaults(self):
        from openquery.models.br.confef import ConfefResult
        r = ConfefResult(cref_number="123456-G/SP")
        assert r.cref_number == "123456-G/SP"
        assert r.nome == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.br.confef import ConfefResult
        r = ConfefResult(cref_number="123456-G/SP", nome="Carlos Educador", status="Ativo")
        data = r.model_dump_json()
        r2 = ConfefResult.model_validate_json(data)
        assert r2.status == "Ativo"

    def test_audit_excluded(self):
        from openquery.models.br.confef import ConfefResult
        r = ConfefResult(cref_number="123456-G/SP", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
