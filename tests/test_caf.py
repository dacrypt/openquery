"""Tests for intl.caf — CAF Development Bank data.

Uses mocked BrowserManager to avoid real browser usage.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestCafResult — model tests
# ===========================================================================


class TestCafResult:
    def test_defaults(self):
        from openquery.models.intl.caf import CafResult

        r = CafResult()
        assert r.search_term == ""
        assert r.indicator == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.caf import CafDataPoint, CafResult

        r = CafResult(
            search_term="Colombia",
            indicator="infrastructure",
            data_points=[
                CafDataPoint(period="2022", value="45.3"),
            ],
        )
        dumped = r.model_dump_json()
        restored = CafResult.model_validate_json(dumped)
        assert restored.search_term == "Colombia"
        assert restored.indicator == "infrastructure"
        assert len(restored.data_points) == 1

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.caf import CafResult

        r = CafResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.caf import CafDataPoint

        dp = CafDataPoint()
        assert dp.period == ""
        assert dp.value == ""


# ===========================================================================
# TestCafSourceMeta
# ===========================================================================


class TestCafSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.caf import CafSource

        meta = CafSource().meta()
        assert meta.name == "intl.caf"

    def test_meta_country(self):
        from openquery.sources.intl.caf import CafSource

        meta = CafSource().meta()
        assert meta.country == "INTL"

    def test_meta_requires_browser(self):
        from openquery.sources.intl.caf import CafSource

        meta = CafSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.caf import CafSource

        meta = CafSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.caf import CafSource

        meta = CafSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestCafParseResult
# ===========================================================================


class TestCafParseResult:
    def _make_input(self, search_term: str = "Colombia", indicator: str = "") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"search_term": search_term, "indicator": indicator},
        )

    def _make_mock_browser(self, rows_data: list[tuple[str, str]], heading: str = "") -> MagicMock:
        mock_heading = MagicMock()
        mock_heading.inner_text.return_value = heading

        mock_rows = []
        for period, value in rows_data:
            c1 = MagicMock()
            c1.inner_text.return_value = period
            c2 = MagicMock()
            c2.inner_text.return_value = value
            row = MagicMock()
            row.query_selector_all.return_value = [c1, c2]
            mock_rows.append(row)

        mock_page = MagicMock()
        mock_page.goto = MagicMock()
        mock_page.wait_for_timeout = MagicMock()
        mock_page.keyboard = MagicMock()
        mock_page.query_selector_all.return_value = mock_rows
        mock_page.query_selector.return_value = MagicMock()  # search input
        mock_page.query_selector.side_effect = lambda sel: (
            MagicMock() if "search" in sel or "text" in sel else (mock_heading if heading else None)
        )

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.sync_context.return_value = mock_ctx
        return mock_browser

    def test_successful_query(self):
        from openquery.sources.intl.caf import CafSource

        mock_browser = self._make_mock_browser(
            [("2021", "42.5"), ("2022", "45.3")], heading="CAF Data Report"
        )

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = CafSource()
            result = source.query(self._make_input())

        assert result.search_term == "Colombia"
        assert len(result.data_points) == 2
        assert result.data_points[0].period == "2021"

    def test_missing_search_term_raises(self):
        from openquery.sources.intl.caf import CafSource

        source = CafSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="search term"):
            source.query(inp)

    def test_search_term_from_document_number(self):
        from openquery.sources.intl.caf import CafSource

        mock_browser = self._make_mock_browser([])

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = CafSource()
            inp = QueryInput(
                document_number="Peru",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.search_term == "Peru"

    def test_no_rows_returns_empty_data_points(self):
        from openquery.sources.intl.caf import CafSource

        mock_browser = self._make_mock_browser([])

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = CafSource()
            result = source.query(self._make_input())

        assert result.data_points == []
