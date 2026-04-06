"""Tests for us.bls — Bureau of Labor Statistics time series.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestBlsResult — model tests
# ===========================================================================


class TestBlsResult:
    def test_defaults(self):
        from openquery.models.us.bls import BlsResult

        r = BlsResult()
        assert r.series_id == ""
        assert r.series_name == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.bls import BlsDataPoint, BlsResult

        r = BlsResult(
            series_id="CUUR0000SA0",
            series_name="CPI-U All Items",
            data_points=[
                BlsDataPoint(year="2022", period="January", value="281.148"),
                BlsDataPoint(year="2022", period="February", value="283.716"),
            ],
        )
        dumped = r.model_dump_json()
        restored = BlsResult.model_validate_json(dumped)
        assert restored.series_id == "CUUR0000SA0"
        assert restored.series_name == "CPI-U All Items"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.us.bls import BlsResult

        r = BlsResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.us.bls import BlsDataPoint

        dp = BlsDataPoint()
        assert dp.year == ""
        assert dp.period == ""
        assert dp.value == ""


# ===========================================================================
# TestBlsSourceMeta
# ===========================================================================


class TestBlsSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.bls import BlsSource

        meta = BlsSource().meta()
        assert meta.name == "us.bls"

    def test_meta_country(self):
        from openquery.sources.us.bls import BlsSource

        meta = BlsSource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.bls import BlsSource

        meta = BlsSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.bls import BlsSource

        meta = BlsSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.bls import BlsSource

        meta = BlsSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestBlsParseResult
# ===========================================================================

MOCK_BLS_RESPONSE = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {
        "series": [
            {
                "seriesID": "CUUR0000SA0",
                "data": [
                    {"year": "2022", "period": "M01", "periodName": "January", "value": "281.148"},
                    {"year": "2022", "period": "M02", "periodName": "February", "value": "283.716"},
                ],
            }
        ]
    },
}


class TestBlsParseResult:
    def _make_input(self, series_id: str = "CUUR0000SA0") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"series_id": series_id},
        )

    def test_successful_query(self):
        from openquery.sources.us.bls import BlsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_BLS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            source = BlsSource()
            result = source.query(self._make_input())

        assert result.series_id == "CUUR0000SA0"
        assert result.series_name == "CPI-U All Items"
        assert len(result.data_points) == 2
        assert result.data_points[0].year == "2022"
        assert result.data_points[0].period == "January"
        assert result.data_points[0].value == "281.148"

    def test_missing_series_id_raises(self):
        from openquery.sources.us.bls import BlsSource

        source = BlsSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="series ID"):
            source.query(inp)

    def test_series_id_from_document_number(self):
        from openquery.sources.us.bls import BlsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_BLS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            source = BlsSource()
            inp = QueryInput(
                document_number="CUUR0000SA0",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.series_id == "CUUR0000SA0"

    def test_api_failure_raises_source_error(self):
        from openquery.sources.us.bls import BlsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "REQUEST_FAILED",
            "message": ["Series does not exist"],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            source = BlsSource()
            with pytest.raises(SourceError, match="us.bls"):
                source.query(self._make_input())

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.bls import BlsSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            source = BlsSource()
            with pytest.raises(SourceError, match="us.bls"):
                source.query(self._make_input())
