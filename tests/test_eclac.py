"""Tests for intl.eclac — ECLAC/CEPAL Latin America statistics.

Uses mocked BrowserManager to avoid real browser usage.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestEclacResult — model tests
# ===========================================================================


class TestEclacResult:
    def test_defaults(self):
        from openquery.models.intl.eclac import EclacResult

        r = EclacResult()
        assert r.indicator == ""
        assert r.country_code == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.eclac import EclacDataPoint, EclacResult

        r = EclacResult(
            indicator="POVERTY_RATE",
            country_code="CO",
            data_points=[
                EclacDataPoint(period="2022", value="39.0"),
                EclacDataPoint(period="2021", value="42.5"),
            ],
        )
        dumped = r.model_dump_json()
        restored = EclacResult.model_validate_json(dumped)
        assert restored.indicator == "POVERTY_RATE"
        assert restored.country_code == "CO"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.eclac import EclacResult

        r = EclacResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.eclac import EclacDataPoint

        dp = EclacDataPoint()
        assert dp.period == ""
        assert dp.value == ""


# ===========================================================================
# TestEclacSourceMeta
# ===========================================================================


class TestEclacSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.eclac import EclacSource

        meta = EclacSource().meta()
        assert meta.name == "intl.eclac"

    def test_meta_country(self):
        from openquery.sources.intl.eclac import EclacSource

        meta = EclacSource().meta()
        assert meta.country == "INTL"

    def test_meta_requires_browser(self):
        from openquery.sources.intl.eclac import EclacSource

        meta = EclacSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.eclac import EclacSource

        meta = EclacSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.eclac import EclacSource

        meta = EclacSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestEclacParseResult
# ===========================================================================

MOCK_PAGE_JSON = '{"body": {"indicator_name": "Poverty rate", "data": [{"year": 2021, "value": 42.5}, {"year": 2022, "value": 39.0}]}}'  # noqa: E501


class TestEclacParseResult:
    def _make_input(self, indicator: str = "POVERTY_RATE", country: str = "CO") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": indicator, "country": country},
        )

    def _make_mock_browser(self, page_content: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.content.return_value = page_content
        mock_page.goto = MagicMock()

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.sync_context.return_value = mock_ctx
        return mock_browser

    def test_successful_query(self):
        from openquery.sources.intl.eclac import EclacSource

        mock_browser = self._make_mock_browser(MOCK_PAGE_JSON)

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = EclacSource()
            result = source.query(self._make_input())

        assert result.indicator == "POVERTY_RATE"
        assert result.country_code == "CO"
        assert result.details == "Poverty rate"
        assert len(result.data_points) == 2

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.eclac import EclacSource

        source = EclacSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="indicator"):
            source.query(inp)

    def test_indicator_from_document_number(self):
        from openquery.sources.intl.eclac import EclacSource

        mock_browser = self._make_mock_browser("{}")

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = EclacSource()
            inp = QueryInput(
                document_number="POVERTY_RATE",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.indicator == "POVERTY_RATE"

    def test_empty_page_returns_empty_data_points(self):
        from openquery.sources.intl.eclac import EclacSource

        mock_browser = self._make_mock_browser("<html><body>No data</body></html>")

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = EclacSource()
            result = source.query(self._make_input())

        assert result.data_points == []
