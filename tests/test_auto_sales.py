"""Tests for us.auto_sales — US vehicle sales via FRED API."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestAutoSalesResult — model tests
# ===========================================================================


class TestAutoSalesResult:
    def test_defaults(self):
        from openquery.models.us.auto_sales import AutoSalesResult

        r = AutoSalesResult()
        assert r.series_id == ""
        assert r.series_name == ""
        assert r.frequency == "monthly"
        assert r.total_observations == 0
        assert r.data_points == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.auto_sales import AutoSalesDataPoint, AutoSalesResult

        r = AutoSalesResult(
            series_id="TOTALSA",
            series_name="Total Vehicle Sales",
            total_observations=2,
            data_points=[
                AutoSalesDataPoint(date="2024-01-01", value="15.8"),
                AutoSalesDataPoint(date="2024-02-01", value="16.2"),
            ],
        )
        dumped = r.model_dump_json()
        restored = AutoSalesResult.model_validate_json(dumped)
        assert restored.series_id == "TOTALSA"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.us.auto_sales import AutoSalesResult

        r = AutoSalesResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.us.auto_sales import AutoSalesDataPoint

        dp = AutoSalesDataPoint()
        assert dp.date == ""
        assert dp.value == ""
        assert dp.units == "millions of units, SAAR"


# ===========================================================================
# TestAutoSalesSourceMeta
# ===========================================================================


class TestAutoSalesSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        meta = AutoSalesSource().meta()
        assert meta.name == "us.auto_sales"

    def test_meta_country(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        meta = AutoSalesSource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        meta = AutoSalesSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        meta = AutoSalesSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        meta = AutoSalesSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestAutoSalesParseResult
# ===========================================================================

MOCK_FRED_SERIES_RESPONSE = {
    "seriess": [
        {
            "id": "TOTALSA",
            "title": "Total Vehicle Sales",
            "frequency_short": "M",
        }
    ]
}

MOCK_FRED_OBS_RESPONSE = {
    "observations": [
        {"date": "2024-02-01", "value": "16.2"},
        {"date": "2024-01-01", "value": "15.8"},
    ]
}


class TestAutoSalesParseResult:
    def _make_input(self, series_id: str = "TOTALSA") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"series_id": series_id},
        )

    def _make_mock_client(self, series_resp, obs_resp) -> MagicMock:
        mock_series = MagicMock()
        mock_series.json.return_value = series_resp
        mock_series.raise_for_status = MagicMock()

        mock_obs = MagicMock()
        mock_obs.json.return_value = obs_resp
        mock_obs.raise_for_status = MagicMock()

        mock_client = MagicMock()
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_series
            return mock_obs

        mock_client.get.side_effect = side_effect
        return mock_client

    def test_successful_query(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        mock_client = self._make_mock_client(MOCK_FRED_SERIES_RESPONSE, MOCK_FRED_OBS_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = AutoSalesSource()
            result = source.query(self._make_input())

        assert result.series_id == "TOTALSA"
        assert result.series_name == "Total Vehicle Sales"
        assert result.total_observations == 2
        # reversed: chronological order
        assert result.data_points[0].date == "2024-01-01"
        assert result.data_points[0].value == "15.8"

    def test_default_series_id(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        mock_client = self._make_mock_client(MOCK_FRED_SERIES_RESPONSE, MOCK_FRED_OBS_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = AutoSalesSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.series_id == "TOTALSA"

    def test_missing_value_replaced_with_empty(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        obs_with_dot = {"observations": [{"date": "2024-01-01", "value": "."}]}
        mock_client = self._make_mock_client(MOCK_FRED_SERIES_RESPONSE, obs_with_dot)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = AutoSalesSource()
            result = source.query(self._make_input())

        assert result.data_points[0].value == ""

    def test_light_auto_series(self):
        from openquery.sources.us.auto_sales import AutoSalesSource

        lautosa_series = {
            "seriess": [
                {"id": "LAUTOSA", "title": "Light Weight Vehicle Sales", "frequency_short": "M"}
            ]
        }
        mock_client = self._make_mock_client(lautosa_series, MOCK_FRED_OBS_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = AutoSalesSource()
            result = source.query(self._make_input("LAUTOSA"))

        assert result.series_id == "LAUTOSA"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.auto_sales import AutoSalesSource

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = AutoSalesSource()
            with pytest.raises(SourceError, match="us.auto_sales"):
                source.query(self._make_input())
