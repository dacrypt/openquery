"""Tests for pe.produce — PRODUCE fisheries/industry source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestProduceSourceMeta:
    def test_meta(self):
        from openquery.sources.pe.produce import ProduceSource
        meta = ProduceSource().meta()
        assert meta.name == "pe.produce"
        assert meta.country == "PE"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.pe.produce import ProduceSource
        src = ProduceSource()
        with pytest.raises(SourceError, match="company_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestProduceModel:
    def test_model_defaults(self):
        from openquery.models.pe.produce import ProduceResult
        r = ProduceResult(search_term="Pesquera Austral")
        assert r.search_term == "Pesquera Austral"
        assert r.company_name == ""
        assert r.registration_status == ""

    def test_model_roundtrip(self):
        from openquery.models.pe.produce import ProduceResult
        r = ProduceResult(search_term="test", company_name="Empresa X", registration_status="Registrada")  # noqa: E501
        data = r.model_dump_json()
        r2 = ProduceResult.model_validate_json(data)
        assert r2.registration_status == "Registrada"

    def test_audit_excluded(self):
        from openquery.models.pe.produce import ProduceResult
        r = ProduceResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
