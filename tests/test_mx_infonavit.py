"""Tests for mx.infonavit — INFONAVIT housing credit source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestInfonavitSourceMeta:
    def test_meta(self):
        from openquery.sources.mx.infonavit import InfonavitSource
        meta = InfonavitSource().meta()
        assert meta.name == "mx.infonavit"
        assert meta.country == "MX"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_nss_raises(self):
        from openquery.sources.mx.infonavit import InfonavitSource
        src = InfonavitSource()
        with pytest.raises(SourceError, match="NSS"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestInfonavitModel:
    def test_model_defaults(self):
        from openquery.models.mx.infonavit import InfonavitResult
        r = InfonavitResult(nss="12345678901")
        assert r.nss == "12345678901"
        assert r.credit_status == ""
        assert r.balance == ""

    def test_model_roundtrip(self):
        from openquery.models.mx.infonavit import InfonavitResult
        r = InfonavitResult(nss="12345678901", credit_status="Activo", balance="$150,000")
        data = r.model_dump_json()
        r2 = InfonavitResult.model_validate_json(data)
        assert r2.credit_status == "Activo"

    def test_audit_excluded(self):
        from openquery.models.mx.infonavit import InfonavitResult
        r = InfonavitResult(nss="12345678901", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
