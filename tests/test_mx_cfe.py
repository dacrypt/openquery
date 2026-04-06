"""Tests for mx.cfe — CFE electricity account source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCfeSourceMeta:
    def test_meta(self):
        from openquery.sources.mx.cfe import CfeSource
        meta = CfeSource().meta()
        assert meta.name == "mx.cfe"
        assert meta.country == "MX"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_service_number_raises(self):
        from openquery.sources.mx.cfe import CfeSource
        src = CfeSource()
        with pytest.raises(SourceError, match="[Ss]ervice number"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestCfeModel:
    def test_model_defaults(self):
        from openquery.models.mx.cfe import CfeResult
        r = CfeResult(service_number="501-123-456-7")
        assert r.service_number == "501-123-456-7"
        assert r.account_status == ""
        assert r.balance == ""

    def test_model_roundtrip(self):
        from openquery.models.mx.cfe import CfeResult
        r = CfeResult(service_number="501-123-456-7", account_status="Al corriente", balance="$0.00")  # noqa: E501
        data = r.model_dump_json()
        r2 = CfeResult.model_validate_json(data)
        assert r2.account_status == "Al corriente"

    def test_audit_excluded(self):
        from openquery.models.mx.cfe import CfeResult
        r = CfeResult(service_number="501-123-456-7", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
