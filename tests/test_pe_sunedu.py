"""Tests for pe.sunedu — SUNEDU university accreditation."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSuneduResult:
    def test_defaults(self):
        from openquery.models.pe.sunedu import SuneduResult

        r = SuneduResult()
        assert r.search_term == ""
        assert r.university_name == ""
        assert r.accreditation_status == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.pe.sunedu import SuneduResult

        r = SuneduResult(
            search_term="PUCP",
            university_name="Pontificia Universidad Católica del Perú",
            accreditation_status="Licenciada",
        )
        dumped = r.model_dump_json()
        restored = SuneduResult.model_validate_json(dumped)
        assert restored.search_term == "PUCP"
        assert restored.accreditation_status == "Licenciada"

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.sunedu import SuneduResult

        r = SuneduResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestSuneduSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pe.sunedu import SuneduSource

        assert SuneduSource().meta().name == "pe.sunedu"

    def test_meta_country(self):
        from openquery.sources.pe.sunedu import SuneduSource

        assert SuneduSource().meta().country == "PE"

    def test_meta_supports_custom(self):
        from openquery.sources.pe.sunedu import SuneduSource

        assert DocumentType.CUSTOM in SuneduSource().meta().supported_inputs

    def test_meta_requires_browser(self):
        from openquery.sources.pe.sunedu import SuneduSource

        assert SuneduSource().meta().requires_browser is True


class TestSuneduParseResult:
    def _make_input(self, name: str = "PUCP") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"university_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.pe.sunedu import SuneduSource

        with pytest.raises(SourceError, match="pe.sunedu"):
            SuneduSource().query(QueryInput(document_number="", document_type=DocumentType.CUSTOM))

    def test_query_returns_result(self):
        from openquery.sources.pe.sunedu import SuneduSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "PUCP — Pontificia Universidad Católica del Perú\nLicenciada"  # noqa: E501
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = SuneduSource().query(self._make_input())

        assert result.search_term == "PUCP"
        assert isinstance(result.queried_at, datetime)
