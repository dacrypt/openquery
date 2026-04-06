"""Tests for intl.ilo — ILO labor statistics."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestIloResult:
    def test_defaults(self):
        from openquery.models.intl.ilo import IloResult

        r = IloResult()
        assert r.country_code == ""
        assert r.indicator == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.ilo import IloDataPoint, IloResult

        r = IloResult(
            country_code="CO",
            indicator="UNE_TUNE_SEX_AGE_NB",
            data_points=[IloDataPoint(period="2022", value="1200000")],
        )
        dumped = r.model_dump_json()
        restored = IloResult.model_validate_json(dumped)
        assert restored.country_code == "CO"
        assert len(restored.data_points) == 1

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.ilo import IloResult

        r = IloResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()

    def test_data_point_defaults(self):
        from openquery.models.intl.ilo import IloDataPoint

        dp = IloDataPoint()
        assert dp.period == ""
        assert dp.value == ""


class TestIloSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.ilo import IloSource

        assert IloSource().meta().name == "intl.ilo"

    def test_meta_country(self):
        from openquery.sources.intl.ilo import IloSource

        assert IloSource().meta().country == "INTL"

    def test_meta_supports_custom(self):
        from openquery.sources.intl.ilo import IloSource

        assert DocumentType.CUSTOM in IloSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.intl.ilo import IloSource

        assert IloSource().meta().rate_limit_rpm == 10


class TestIloParseResult:
    def _make_input(self, country: str = "CO", indicator: str = "UNE_TUNE_SEX_AGE_NB") -> QueryInput:  # noqa: E501
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "indicator": indicator},
        )

    def test_missing_country_raises(self):
        from openquery.sources.intl.ilo import IloSource

        with pytest.raises(SourceError, match="country"):
            IloSource().query(
                QueryInput(
                    document_number="",
                    document_type=DocumentType.CUSTOM,
                    extra={"indicator": "UNE_TUNE_SEX_AGE_NB"},
                )
            )

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.ilo import IloSource

        with pytest.raises(SourceError, match="indicator"):
            IloSource().query(
                QueryInput(
                    document_number="CO",
                    document_type=DocumentType.CUSTOM,
                    extra={},
                )
            )

    def test_query_returns_result(self):
        from openquery.sources.intl.ilo import IloSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = "ILO STAT data for Colombia"
        mock_page.query_selector_all.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.new_page.return_value = mock_page

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.sync_context.return_value = mock_ctx
            result = IloSource().query(self._make_input())

        assert result.country_code == "CO"
        assert result.indicator == "UNE_TUNE_SEX_AGE_NB"
