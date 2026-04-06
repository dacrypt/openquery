"""Tests for ar.enacom — ENACOM telecom regulator source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestEnacomSourceMeta:
    def test_meta(self):
        from openquery.sources.ar.enacom import EnacomSource
        meta = EnacomSource().meta()
        assert meta.name == "ar.enacom"
        assert meta.country == "AR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.ar.enacom import EnacomSource
        src = EnacomSource()
        with pytest.raises(SourceError, match="company_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestEnacomModel:
    def test_model_defaults(self):
        from openquery.models.ar.enacom import EnacomResult
        r = EnacomResult(search_term="Telecom")
        assert r.search_term == "Telecom"
        assert r.company_name == ""
        assert r.license_status == ""

    def test_model_roundtrip(self):
        from openquery.models.ar.enacom import EnacomResult
        r = EnacomResult(search_term="Telecom", company_name="Telecom Argentina", license_status="Habilitado")  # noqa: E501
        data = r.model_dump_json()
        r2 = EnacomResult.model_validate_json(data)
        assert r2.license_status == "Habilitado"

    def test_audit_excluded(self):
        from openquery.models.ar.enacom import EnacomResult
        r = EnacomResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
