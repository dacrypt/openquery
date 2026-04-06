"""Tests for co.crc — CRC telecom regulator."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCrcResult:
    def test_defaults(self):
        from openquery.models.co.crc import CrcResult

        r = CrcResult()
        assert r.search_term == ""
        assert r.operator_name == ""
        assert r.license_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.crc import CrcResult

        r = CrcResult(
            search_term="Claro",
            operator_name="Claro Colombia SA",
            license_status="Habilitado",
        )
        dumped = r.model_dump_json()
        restored = CrcResult.model_validate_json(dumped)
        assert restored.search_term == "Claro"
        assert restored.license_status == "Habilitado"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.crc import CrcResult

        r = CrcResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestCrcSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.crc import CrcSource

        assert CrcSource().meta().name == "co.crc"

    def test_meta_country(self):
        from openquery.sources.co.crc import CrcSource

        assert CrcSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.crc import CrcSource

        assert DocumentType.CUSTOM in CrcSource().meta().supported_inputs


class TestCrcParseResult:
    def _make_input(self, name: str = "Claro") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"operator_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.co.crc import CrcSource

        with pytest.raises(SourceError, match="co.crc"):
            CrcSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.co.crc import CrcSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Claro Colombia SA\nHabilitado"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = CrcSource().query(self._make_input())

        assert result.search_term == "Claro"
