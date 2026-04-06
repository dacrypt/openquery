"""Tests for pe.midis — MIDIS social programs beneficiary source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMidisSourceMeta:
    def test_meta(self):
        from openquery.sources.pe.midis import MidisSource
        meta = MidisSource().meta()
        assert meta.name == "pe.midis"
        assert meta.country == "PE"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dni_raises(self):
        from openquery.sources.pe.midis import MidisSource
        src = MidisSource()
        with pytest.raises(SourceError, match="DNI"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestMidisModel:
    def test_model_defaults(self):
        from openquery.models.pe.midis import MidisResult
        r = MidisResult(dni="12345678")
        assert r.dni == "12345678"
        assert r.nombre == ""
        assert r.programs == []

    def test_model_roundtrip(self):
        from openquery.models.pe.midis import MidisResult
        r = MidisResult(dni="12345678", nombre="Juan Pérez", programs=["Pensión 65"])
        data = r.model_dump_json()
        r2 = MidisResult.model_validate_json(data)
        assert r2.programs == ["Pensión 65"]

    def test_audit_excluded(self):
        from openquery.models.pe.midis import MidisResult
        r = MidisResult(dni="12345678", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
