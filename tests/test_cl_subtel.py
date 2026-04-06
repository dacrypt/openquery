"""Tests for cl.subtel — SUBTEL telecom operators source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSubtelSourceMeta:
    def test_meta(self):
        from openquery.sources.cl.subtel import SubtelSource
        meta = SubtelSource().meta()
        assert meta.name == "cl.subtel"
        assert meta.country == "CL"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.cl.subtel import SubtelSource
        src = SubtelSource()
        with pytest.raises(SourceError, match="operator_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSubtelModel:
    def test_model_defaults(self):
        from openquery.models.cl.subtel import SubtelResult
        r = SubtelResult(search_term="Entel")
        assert r.search_term == "Entel"
        assert r.operator_name == ""
        assert r.license_status == ""

    def test_model_roundtrip(self):
        from openquery.models.cl.subtel import SubtelResult
        r = SubtelResult(search_term="Entel", operator_name="Entel S.A.", license_status="Autorizado")  # noqa: E501
        data = r.model_dump_json()
        r2 = SubtelResult.model_validate_json(data)
        assert r2.license_status == "Autorizado"

    def test_audit_excluded(self):
        from openquery.models.cl.subtel import SubtelResult
        r = SubtelResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
