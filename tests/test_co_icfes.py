"""Tests for co.icfes — ICFES exam results."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestIcfesResult:
    def test_defaults(self):
        from openquery.models.co.icfes import IcfesResult

        r = IcfesResult()
        assert r.documento == ""
        assert r.nombre == ""
        assert r.exam_type == ""
        assert r.score == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.icfes import IcfesResult

        r = IcfesResult(
            documento="12345678",
            nombre="Juan Perez",
            exam_type="Saber Pro",
            score="350",
        )
        dumped = r.model_dump_json()
        restored = IcfesResult.model_validate_json(dumped)
        assert restored.documento == "12345678"
        assert restored.nombre == "Juan Perez"
        assert restored.exam_type == "Saber Pro"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.icfes import IcfesResult

        r = IcfesResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


class TestIcfesSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.icfes import IcfesSource

        assert IcfesSource().meta().name == "co.icfes"

    def test_meta_country(self):
        from openquery.sources.co.icfes import IcfesSource

        assert IcfesSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        from openquery.sources.co.icfes import IcfesSource

        meta = IcfesSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supports_cedula(self):
        from openquery.sources.co.icfes import IcfesSource

        assert DocumentType.CEDULA in IcfesSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.co.icfes import IcfesSource

        assert IcfesSource().meta().rate_limit_rpm == 10


class TestIcfesParseResult:
    def _make_input(self, documento: str = "12345678") -> QueryInput:
        return QueryInput(document_number=documento, document_type=DocumentType.CEDULA)

    def test_empty_document_raises(self):
        from openquery.sources.co.icfes import IcfesSource

        with pytest.raises(SourceError, match="co.icfes"):
            IcfesSource().query(QueryInput(document_number="", document_type=DocumentType.CEDULA))

    def test_browser_query_returns_result(self):
        from openquery.sources.co.icfes import IcfesSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Nombre: Juan Perez\nSaber Pro\nPuntaje: 350"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            source = IcfesSource()
            result = source.query(self._make_input())

        assert result.documento == "12345678"
        assert isinstance(result.queried_at, datetime)
