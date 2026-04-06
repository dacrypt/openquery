"""Tests for co.superfinanciera_seguros — Superfinanciera insurance companies."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSuperfinancieraSegurosResult:
    def test_defaults(self):
        from openquery.models.co.superfinanciera_seguros import SuperfinancieraSegurosResult

        r = SuperfinancieraSegurosResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.entity_type == ""
        assert r.status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.superfinanciera_seguros import SuperfinancieraSegurosResult

        r = SuperfinancieraSegurosResult(
            search_term="Sura",
            company_name="Seguros de Vida Suramericana SA",
            entity_type="Aseguradora",
            status="Activa",
        )
        dumped = r.model_dump_json()
        restored = SuperfinancieraSegurosResult.model_validate_json(dumped)
        assert restored.search_term == "Sura"
        assert restored.status == "Activa"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.superfinanciera_seguros import SuperfinancieraSegurosResult

        r = SuperfinancieraSegurosResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestSuperfinancieraSegurosSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.superfinanciera_seguros import SuperfinancieraSegurosSource

        assert SuperfinancieraSegurosSource().meta().name == "co.superfinanciera_seguros"

    def test_meta_country(self):
        from openquery.sources.co.superfinanciera_seguros import SuperfinancieraSegurosSource

        assert SuperfinancieraSegurosSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.superfinanciera_seguros import SuperfinancieraSegurosSource

        assert DocumentType.CUSTOM in SuperfinancieraSegurosSource().meta().supported_inputs


class TestSuperfinancieraSegurosParseResult:
    def _make_input(self, name: str = "Sura") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"company_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.co.superfinanciera_seguros import SuperfinancieraSegurosSource

        with pytest.raises(SourceError, match="co.superfinanciera_seguros"):
            SuperfinancieraSegurosSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.co.superfinanciera_seguros import SuperfinancieraSegurosSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Sura — asegurador vigente"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = SuperfinancieraSegurosSource().query(self._make_input())

        assert result.search_term == "Sura"
