"""Tests for br.cfc — CFC accountant registry source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCfcSourceMeta:
    def test_meta(self):
        from openquery.sources.br.cfc import CfcSource
        meta = CfcSource().meta()
        assert meta.name == "br.cfc"
        assert meta.country == "BR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_crc_raises(self):
        from openquery.sources.br.cfc import CfcSource
        src = CfcSource()
        with pytest.raises(SourceError, match="CRC"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestCfcModel:
    def test_model_defaults(self):
        from openquery.models.br.cfc import CfcResult
        r = CfcResult(crc_number="SP-123456/O-1")
        assert r.crc_number == "SP-123456/O-1"
        assert r.nome == ""
        assert r.status == ""

    def test_model_roundtrip(self):
        from openquery.models.br.cfc import CfcResult
        r = CfcResult(crc_number="SP-123456/O-1", nome="Maria Contadora", status="Ativo")
        data = r.model_dump_json()
        r2 = CfcResult.model_validate_json(data)
        assert r2.status == "Ativo"

    def test_audit_excluded(self):
        from openquery.models.br.cfc import CfcResult
        r = CfcResult(crc_number="SP-123456/O-1", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
