"""Tests for ec.superintendencia_bancos — Ecuador Superbancos source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestEcSuperintendenciaBancosSourceMeta:
    def test_meta(self):
        from openquery.sources.ec.superintendencia_bancos import EcSuperintendenciaBancosSource
        meta = EcSuperintendenciaBancosSource().meta()
        assert meta.name == "ec.superintendencia_bancos"
        assert meta.country == "EC"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_ruc_raises(self):
        from openquery.sources.ec.superintendencia_bancos import EcSuperintendenciaBancosSource
        src = EcSuperintendenciaBancosSource()
        with pytest.raises(SourceError, match="RUC"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestEcSuperintendenciaBancosModel:
    def test_model_defaults(self):
        from openquery.models.ec.superintendencia_bancos import EcSuperintendenciaBancosResult
        r = EcSuperintendenciaBancosResult(ruc="1791234567001")
        assert r.ruc == "1791234567001"
        assert r.entity_name == ""
        assert r.entity_type == ""

    def test_model_roundtrip(self):
        from openquery.models.ec.superintendencia_bancos import EcSuperintendenciaBancosResult
        r = EcSuperintendenciaBancosResult(ruc="1791234567001", entity_name="Banco XYZ", entity_type="Banco Privado")  # noqa: E501
        data = r.model_dump_json()
        r2 = EcSuperintendenciaBancosResult.model_validate_json(data)
        assert r2.entity_name == "Banco XYZ"

    def test_audit_excluded(self):
        from openquery.models.ec.superintendencia_bancos import EcSuperintendenciaBancosResult
        r = EcSuperintendenciaBancosResult(ruc="1791234567001", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
