"""Tests for us.osha — OSHA workplace inspections and violations.

Uses mocked BrowserManager to avoid real browser usage.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestOshaResult — model tests
# ===========================================================================


class TestOshaResult:
    def test_defaults(self):
        from openquery.models.us.osha import OshaResult

        r = OshaResult()
        assert r.search_term == ""
        assert r.total_inspections == 0
        assert r.violations == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.osha import OshaResult, OshaViolation

        r = OshaResult(
            search_term="Acme Corp",
            total_inspections=3,
            violations=[
                OshaViolation(
                    citation_id="01-001",
                    description="Lack of guardrails",
                    penalty="$7500",
                    severity="Serious",
                ),
            ],
        )
        dumped = r.model_dump_json()
        restored = OshaResult.model_validate_json(dumped)
        assert restored.search_term == "Acme Corp"
        assert restored.total_inspections == 3
        assert len(restored.violations) == 1
        assert restored.violations[0].citation_id == "01-001"

    def test_audit_excluded_from_json(self):
        from openquery.models.us.osha import OshaResult

        r = OshaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_violation_defaults(self):
        from openquery.models.us.osha import OshaViolation

        v = OshaViolation()
        assert v.citation_id == ""
        assert v.description == ""
        assert v.penalty == ""
        assert v.severity == ""


# ===========================================================================
# TestOshaSourceMeta
# ===========================================================================


class TestOshaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.osha import OshaSource

        meta = OshaSource().meta()
        assert meta.name == "us.osha"

    def test_meta_country(self):
        from openquery.sources.us.osha import OshaSource

        meta = OshaSource().meta()
        assert meta.country == "US"

    def test_meta_requires_browser(self):
        from openquery.sources.us.osha import OshaSource

        meta = OshaSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.osha import OshaSource

        meta = OshaSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.us.osha import OshaSource

        meta = OshaSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestOshaParseResult
# ===========================================================================


class TestOshaParseResult:
    def _make_input(self, company: str = "Acme Corp") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"company_name": company},
        )

    def _make_mock_browser(
        self, rows_data: list[tuple[str, str, str, str]]
    ) -> MagicMock:
        mock_rows = []
        for citation, description, penalty, severity in rows_data:
            cells = []
            for text in (citation, description, penalty, severity):
                cell = MagicMock()
                cell.inner_text.return_value = text
                cells.append(cell)
            row = MagicMock()
            row.query_selector_all.return_value = cells
            mock_rows.append(row)

        mock_name_input = MagicMock()
        mock_submit = MagicMock()

        mock_page = MagicMock()
        mock_page.goto = MagicMock()
        mock_page.wait_for_load_state = MagicMock()
        mock_page.query_selector_all.return_value = mock_rows
        mock_page.query_selector.side_effect = lambda sel: (
            mock_name_input if "estab" in sel or "name" in sel.lower() else mock_submit
        )

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.sync_context.return_value = mock_ctx
        return mock_browser

    def test_successful_query(self):
        from openquery.sources.us.osha import OshaSource

        mock_browser = self._make_mock_browser(
            [
                ("01-001", "Lack of guardrails", "$7500", "Serious"),
                ("01-002", "No hard hats", "$3500", "Other"),
            ]
        )

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = OshaSource()
            result = source.query(self._make_input())

        assert result.search_term == "Acme Corp"
        assert result.total_inspections == 2
        assert len(result.violations) == 2
        assert result.violations[0].citation_id == "01-001"
        assert result.violations[0].description == "Lack of guardrails"
        assert result.violations[0].penalty == "$7500"

    def test_missing_company_raises(self):
        from openquery.sources.us.osha import OshaSource

        source = OshaSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="company name"):
            source.query(inp)

    def test_company_from_document_number(self):
        from openquery.sources.us.osha import OshaSource

        mock_browser = self._make_mock_browser([])

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = OshaSource()
            inp = QueryInput(
                document_number="Acme Corp",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.search_term == "Acme Corp"

    def test_no_rows_returns_empty_violations(self):
        from openquery.sources.us.osha import OshaSource

        mock_browser = self._make_mock_browser([])

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = OshaSource()
            result = source.query(self._make_input())

        assert result.violations == []
        assert result.total_inspections == 0

    def test_details_contains_company_name(self):
        from openquery.sources.us.osha import OshaSource

        mock_browser = self._make_mock_browser([])

        with patch("openquery.core.browser.BrowserManager", return_value=mock_browser):
            source = OshaSource()
            result = source.query(self._make_input())

        assert "Acme Corp" in result.details
