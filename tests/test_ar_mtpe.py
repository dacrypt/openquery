"""Tests for ar.mtpe — Argentina MTEySS employer lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMtpeResult:
    def test_defaults(self):
        from openquery.models.ar.mtpe import MtpeResult

        r = MtpeResult()
        assert r.cuit == ""
        assert r.employer_name == ""
        assert r.registration_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ar.mtpe import MtpeResult

        r = MtpeResult(
            cuit="30-12345678-9",
            employer_name="Empresa SA",
            registration_status="Registrado",
        )
        dumped = r.model_dump_json()
        restored = MtpeResult.model_validate_json(dumped)
        assert restored.cuit == "30-12345678-9"
        assert restored.registration_status == "Registrado"

    def test_audit_excluded_from_json(self):
        from openquery.models.ar.mtpe import MtpeResult

        r = MtpeResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestMtpeSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ar.mtpe import MtpeSource

        assert MtpeSource().meta().name == "ar.mtpe"

    def test_meta_country(self):
        from openquery.sources.ar.mtpe import MtpeSource

        assert MtpeSource().meta().country == "AR"

    def test_meta_supports_custom(self):
        from openquery.sources.ar.mtpe import MtpeSource

        assert DocumentType.CUSTOM in MtpeSource().meta().supported_inputs


class TestMtpeParseResult:
    def _make_input(self, cuit: str = "30-12345678-9") -> QueryInput:
        return QueryInput(
            document_number=cuit,
            document_type=DocumentType.CUSTOM,
            extra={"cuit": cuit},
        )

    def test_empty_cuit_raises(self):
        from openquery.sources.ar.mtpe import MtpeSource

        with pytest.raises(SourceError, match="ar.mtpe"):
            MtpeSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.ar.mtpe import MtpeSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Razón social: Empresa SA\nRegistrado"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = MtpeSource().query(self._make_input())

        assert result.cuit == "30-12345678-9"
