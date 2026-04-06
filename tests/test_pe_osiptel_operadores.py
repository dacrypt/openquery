"""Tests for pe.osiptel_operadores — OSIPTEL licensed operators."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestOsiptelOperadoresResult:
    def test_defaults(self):
        from openquery.models.pe.osiptel_operadores import OsiptelOperadoresResult

        r = OsiptelOperadoresResult()
        assert r.search_term == ""
        assert r.operator_name == ""
        assert r.service_type == ""
        assert r.license_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pe.osiptel_operadores import OsiptelOperadoresResult

        r = OsiptelOperadoresResult(
            search_term="Claro",
            operator_name="Claro Peru SAC",
            service_type="Telefonía móvil",
            license_status="Concesionado",
        )
        dumped = r.model_dump_json()
        restored = OsiptelOperadoresResult.model_validate_json(dumped)
        assert restored.search_term == "Claro"
        assert restored.license_status == "Concesionado"

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.osiptel_operadores import OsiptelOperadoresResult

        r = OsiptelOperadoresResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestOsiptelOperadoresSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pe.osiptel_operadores import OsiptelOperadoresSource

        assert OsiptelOperadoresSource().meta().name == "pe.osiptel_operadores"

    def test_meta_country(self):
        from openquery.sources.pe.osiptel_operadores import OsiptelOperadoresSource

        assert OsiptelOperadoresSource().meta().country == "PE"

    def test_meta_supports_custom(self):
        from openquery.sources.pe.osiptel_operadores import OsiptelOperadoresSource

        assert DocumentType.CUSTOM in OsiptelOperadoresSource().meta().supported_inputs


class TestOsiptelOperadoresParseResult:
    def _make_input(self, name: str = "Claro") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"operator_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.pe.osiptel_operadores import OsiptelOperadoresSource

        with pytest.raises(SourceError, match="pe.osiptel_operadores"):
            OsiptelOperadoresSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.pe.osiptel_operadores import OsiptelOperadoresSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Claro Peru SAC\nTelefonía móvil\nConcesionado"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = OsiptelOperadoresSource().query(self._make_input())

        assert result.search_term == "Claro"
