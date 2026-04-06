"""Tests for ve.conatel — CONATEL telecom regulator source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestConatelSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.conatel import ConatelSource
        meta = ConatelSource().meta()
        assert meta.name == "ve.conatel"
        assert meta.country == "VE"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.ve.conatel import ConatelSource
        src = ConatelSource()
        with pytest.raises(SourceError, match="operator_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestConatelModel:
    def test_model_defaults(self):
        from openquery.models.ve.conatel import ConatelResult
        r = ConatelResult(search_term="CANTV")
        assert r.search_term == "CANTV"
        assert r.operator_name == ""
        assert r.license_status == ""

    def test_model_roundtrip(self):
        from openquery.models.ve.conatel import ConatelResult
        r = ConatelResult(search_term="CANTV", operator_name="CANTV S.A.", license_status="Habilitada")  # noqa: E501
        data = r.model_dump_json()
        r2 = ConatelResult.model_validate_json(data)
        assert r2.license_status == "Habilitada"

    def test_audit_excluded(self):
        from openquery.models.ve.conatel import ConatelResult
        r = ConatelResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
