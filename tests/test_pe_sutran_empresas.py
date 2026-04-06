"""Tests for pe.sutran_empresas — SUTRAN transport companies."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSutranEmpresasResult:
    def test_defaults(self):
        from openquery.models.pe.sutran_empresas import SutranEmpresasResult

        r = SutranEmpresasResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.license_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pe.sutran_empresas import SutranEmpresasResult

        r = SutranEmpresasResult(
            search_term="Transportes Cruz",
            company_name="Transportes Cruz SAC",
            license_status="Habilitada",
        )
        dumped = r.model_dump_json()
        restored = SutranEmpresasResult.model_validate_json(dumped)
        assert restored.search_term == "Transportes Cruz"
        assert restored.license_status == "Habilitada"

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.sutran_empresas import SutranEmpresasResult

        r = SutranEmpresasResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestSutranEmpresasSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pe.sutran_empresas import SutranEmpresasSource

        assert SutranEmpresasSource().meta().name == "pe.sutran_empresas"

    def test_meta_country(self):
        from openquery.sources.pe.sutran_empresas import SutranEmpresasSource

        assert SutranEmpresasSource().meta().country == "PE"

    def test_meta_supports_custom(self):
        from openquery.sources.pe.sutran_empresas import SutranEmpresasSource

        assert DocumentType.CUSTOM in SutranEmpresasSource().meta().supported_inputs


class TestSutranEmpresasParseResult:
    def _make_input(self, name: str = "Transportes Cruz") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"company_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.pe.sutran_empresas import SutranEmpresasSource

        with pytest.raises(SourceError, match="pe.sutran_empresas"):
            SutranEmpresasSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.pe.sutran_empresas import SutranEmpresasSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Transportes Cruz SAC\nHabilitada"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = SutranEmpresasSource().query(self._make_input())

        assert result.search_term == "Transportes Cruz"
