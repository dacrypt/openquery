"""Tests for co.mintrabajo — MinTrabajo labor consultations."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMintrabajoResult:
    def test_defaults(self):
        from openquery.models.co.mintrabajo import MintrabajoResult

        r = MintrabajoResult()
        assert r.nit == ""
        assert r.company_name == ""
        assert r.compliance_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.mintrabajo import MintrabajoResult

        r = MintrabajoResult(
            nit="900123456",
            company_name="Empresa Ejemplo SAS",
            compliance_status="Al día",
        )
        dumped = r.model_dump_json()
        restored = MintrabajoResult.model_validate_json(dumped)
        assert restored.nit == "900123456"
        assert restored.compliance_status == "Al día"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.mintrabajo import MintrabajoResult

        r = MintrabajoResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestMintrabajoSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.mintrabajo import MintrabajoSource

        assert MintrabajoSource().meta().name == "co.mintrabajo"

    def test_meta_country(self):
        from openquery.sources.co.mintrabajo import MintrabajoSource

        assert MintrabajoSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.mintrabajo import MintrabajoSource

        assert DocumentType.CUSTOM in MintrabajoSource().meta().supported_inputs


class TestMintrabajoParseResult:
    def _make_input(self, nit: str = "900123456") -> QueryInput:
        return QueryInput(
            document_number=nit,
            document_type=DocumentType.CUSTOM,
            extra={"nit": nit},
        )

    def test_empty_nit_raises(self):
        from openquery.sources.co.mintrabajo import MintrabajoSource

        with pytest.raises(SourceError, match="co.mintrabajo"):
            MintrabajoSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.co.mintrabajo import MintrabajoSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Empresa: Ejemplo SAS\nEstado: Al día"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = MintrabajoSource().query(self._make_input())

        assert result.nit == "900123456"
