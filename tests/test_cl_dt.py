"""Tests for cl.dt — DT employer lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestDtResult:
    def test_defaults(self):
        from openquery.models.cl.dt import DtResult

        r = DtResult()
        assert r.rut == ""
        assert r.employer_name == ""
        assert r.compliance_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.cl.dt import DtResult

        r = DtResult(
            rut="76.123.456-7",
            employer_name="Empresa Ltda",
            compliance_status="Al día",
        )
        dumped = r.model_dump_json()
        restored = DtResult.model_validate_json(dumped)
        assert restored.rut == "76.123.456-7"
        assert restored.compliance_status == "Al día"

    def test_audit_excluded_from_json(self):
        from openquery.models.cl.dt import DtResult

        r = DtResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestDtSourceMeta:
    def test_meta_name(self):
        from openquery.sources.cl.dt import DtSource

        assert DtSource().meta().name == "cl.dt"

    def test_meta_country(self):
        from openquery.sources.cl.dt import DtSource

        assert DtSource().meta().country == "CL"

    def test_meta_supports_custom(self):
        from openquery.sources.cl.dt import DtSource

        assert DocumentType.CUSTOM in DtSource().meta().supported_inputs


class TestDtParseResult:
    def _make_input(self, rut: str = "76.123.456-7") -> QueryInput:
        return QueryInput(
            document_number=rut,
            document_type=DocumentType.CUSTOM,
            extra={"rut": rut},
        )

    def test_empty_rut_raises(self):
        from openquery.sources.cl.dt import DtSource

        with pytest.raises(SourceError, match="cl.dt"):
            DtSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.cl.dt import DtSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Razón social: Empresa Ltda\nAl día"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = DtSource().query(self._make_input())

        assert result.rut == "76.123.456-7"
