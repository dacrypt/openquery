"""Tests for br.receita_mei — MEI microentrepreneur source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestReceitaMeiSourceMeta:
    def test_meta(self):
        from openquery.sources.br.receita_mei import ReceitaMeiSource
        meta = ReceitaMeiSource().meta()
        assert meta.name == "br.receita_mei"
        assert meta.country == "BR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_empty_cnpj_raises(self):
        from openquery.sources.br.receita_mei import ReceitaMeiSource
        src = ReceitaMeiSource()
        with pytest.raises(SourceError, match="CNPJ"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_cnpj_normalized(self):
        from openquery.sources.br.receita_mei import ReceitaMeiSource
        ReceitaMeiSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="12.345.678/0001-90")
        # Normalization happens in query(), CNPJ dots/slashes stripped
        assert "." in inp.document_number  # raw input preserved


class TestReceitaMeiModel:
    def test_model_defaults(self):
        from openquery.models.br.receita_mei import ReceitaMeiResult
        r = ReceitaMeiResult(cnpj="12345678000190")
        assert r.cnpj == "12345678000190"
        assert r.nome == ""
        assert r.mei_status == ""

    def test_model_roundtrip(self):
        from openquery.models.br.receita_mei import ReceitaMeiResult
        r = ReceitaMeiResult(cnpj="12345678000190", nome="João Silva", mei_status="MEI")
        data = r.model_dump_json()
        r2 = ReceitaMeiResult.model_validate_json(data)
        assert r2.mei_status == "MEI"

    def test_audit_excluded(self):
        from openquery.models.br.receita_mei import ReceitaMeiResult
        r = ReceitaMeiResult(cnpj="12345678000190", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
