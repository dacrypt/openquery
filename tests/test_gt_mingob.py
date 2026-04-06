"""Tests for gt.mingob — MINGOB security companies source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMingobSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.mingob import MingobSource
        meta = MingobSource().meta()
        assert meta.name == "gt.mingob"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.gt.mingob import MingobSource
        src = MingobSource()
        with pytest.raises(SourceError, match="company_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestMingobModel:
    def test_model_defaults(self):
        from openquery.models.gt.mingob import MingobResult
        r = MingobResult(search_term="Seguridad Ixchel")
        assert r.search_term == "Seguridad Ixchel"
        assert r.company_name == ""
        assert r.license_status == ""

    def test_model_roundtrip(self):
        from openquery.models.gt.mingob import MingobResult
        r = MingobResult(search_term="test", company_name="Empresa XYZ", license_status="Autorizada")  # noqa: E501
        data = r.model_dump_json()
        r2 = MingobResult.model_validate_json(data)
        assert r2.license_status == "Autorizada"

    def test_audit_excluded(self):
        from openquery.models.gt.mingob import MingobResult
        r = MingobResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
