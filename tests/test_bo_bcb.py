"""Tests for bo.bcb — BCB central bank exchange rates source."""

from __future__ import annotations

from openquery.sources.base import DocumentType, QueryInput


class TestBcbSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.bcb import BcbSource
        meta = BcbSource().meta()
        assert meta.name == "bo.bcb"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_accepts_any_input(self):
        from openquery.sources.bo.bcb import BcbSource
        BcbSource()
        # BCB accepts any input (no required field)
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        assert inp is not None


class TestBcbModel:
    def test_model_defaults(self):
        from openquery.models.bo.bcb import BcbResult
        r = BcbResult()
        assert r.usd_rate == ""
        assert r.date == ""

    def test_model_roundtrip(self):
        from openquery.models.bo.bcb import BcbResult
        r = BcbResult(usd_rate="6.96", date="2024-01-15")
        data = r.model_dump_json()
        r2 = BcbResult.model_validate_json(data)
        assert r2.usd_rate == "6.96"
        assert r2.date == "2024-01-15"

    def test_audit_excluded(self):
        from openquery.models.bo.bcb import BcbResult
        r = BcbResult(usd_rate="6.96", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
