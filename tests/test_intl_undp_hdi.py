"""Tests for intl.undp_hdi — UNDP Human Development Index."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestUndpHdiResult:
    def test_defaults(self):
        from openquery.models.intl.undp_hdi import UndpHdiResult

        r = UndpHdiResult()
        assert r.country == ""
        assert r.hdi_score == ""
        assert r.hdi_rank == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.undp_hdi import UndpHdiResult

        r = UndpHdiResult(
            country="Colombia",
            hdi_score="0.752",
            hdi_rank="83",
        )
        dumped = r.model_dump_json()
        restored = UndpHdiResult.model_validate_json(dumped)
        assert restored.country == "Colombia"
        assert restored.hdi_score == "0.752"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.undp_hdi import UndpHdiResult

        r = UndpHdiResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestUndpHdiSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.undp_hdi import UndpHdiSource

        assert UndpHdiSource().meta().name == "intl.undp_hdi"

    def test_meta_country(self):
        from openquery.sources.intl.undp_hdi import UndpHdiSource

        assert UndpHdiSource().meta().country == "INTL"

    def test_meta_supports_custom(self):
        from openquery.sources.intl.undp_hdi import UndpHdiSource

        assert DocumentType.CUSTOM in UndpHdiSource().meta().supported_inputs

    def test_meta_requires_browser(self):
        from openquery.sources.intl.undp_hdi import UndpHdiSource

        assert UndpHdiSource().meta().requires_browser is True


class TestUndpHdiParseResult:
    def _make_input(self, country: str = "Colombia") -> QueryInput:
        return QueryInput(
            document_number=country,
            document_type=DocumentType.CUSTOM,
            extra={"country": country},
        )

    def test_empty_country_raises(self):
        from openquery.sources.intl.undp_hdi import UndpHdiSource

        with pytest.raises(SourceError, match="intl.undp_hdi"):
            UndpHdiSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_query_returns_result(self):
        from openquery.sources.intl.undp_hdi import UndpHdiSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Colombia  0.752  83"
        mock_page.query_selector.return_value = None
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = UndpHdiSource().query(self._make_input())

        assert result.country == "Colombia"
        assert isinstance(result.queried_at, datetime)
