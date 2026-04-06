"""Tests for pe.sbs_seguros — SBS insurance companies."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSbsSegurosResult:
    def test_defaults(self):
        from openquery.models.pe.sbs_seguros import SbsSegurosResult

        r = SbsSegurosResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.entity_type == ""
        assert r.status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pe.sbs_seguros import SbsSegurosResult

        r = SbsSegurosResult(
            search_term="Rimac",
            company_name="Rimac Seguros SA",
            entity_type="Empresa de Seguros",
            status="Activa",
        )
        dumped = r.model_dump_json()
        restored = SbsSegurosResult.model_validate_json(dumped)
        assert restored.search_term == "Rimac"
        assert restored.status == "Activa"

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.sbs_seguros import SbsSegurosResult

        r = SbsSegurosResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestSbsSegurosSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pe.sbs_seguros import SbsSegurosSource

        assert SbsSegurosSource().meta().name == "pe.sbs_seguros"

    def test_meta_country(self):
        from openquery.sources.pe.sbs_seguros import SbsSegurosSource

        assert SbsSegurosSource().meta().country == "PE"

    def test_meta_supports_custom(self):
        from openquery.sources.pe.sbs_seguros import SbsSegurosSource

        assert DocumentType.CUSTOM in SbsSegurosSource().meta().supported_inputs


class TestSbsSegurosParseResult:
    def _make_input(self, name: str = "Rimac") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"company_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.pe.sbs_seguros import SbsSegurosSource

        with pytest.raises(SourceError, match="pe.sbs_seguros"):
            SbsSegurosSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.pe.sbs_seguros import SbsSegurosSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Rimac Seguros SA\nseguros activa"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = SbsSegurosSource().query(self._make_input())

        assert result.search_term == "Rimac"
