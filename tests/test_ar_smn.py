"""Tests for ar.smn — SMN weather/climate data source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSmnSourceMeta:
    def test_meta(self):
        from openquery.sources.ar.smn import SmnSource
        meta = SmnSource().meta()
        assert meta.name == "ar.smn"
        assert meta.country == "AR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_empty_city_raises(self):
        from openquery.sources.ar.smn import SmnSource
        src = SmnSource()
        with pytest.raises(SourceError, match="[Cc]ity"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSmnModel:
    def test_model_defaults(self):
        from openquery.models.ar.smn import SmnResult
        r = SmnResult(city="Buenos Aires")
        assert r.city == "Buenos Aires"
        assert r.temperature == ""
        assert r.conditions == ""

    def test_model_roundtrip(self):
        from openquery.models.ar.smn import SmnResult
        r = SmnResult(city="Buenos Aires", temperature="22", conditions="Despejado")
        data = r.model_dump_json()
        r2 = SmnResult.model_validate_json(data)
        assert r2.city == "Buenos Aires"
        assert r2.temperature == "22"

    def test_audit_excluded(self):
        from openquery.models.ar.smn import SmnResult
        r = SmnResult(city="Buenos Aires", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
