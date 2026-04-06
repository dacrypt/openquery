"""Tests for intl.who — WHO Global Health Observatory.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestWhoResult — model tests
# ===========================================================================


class TestWhoResult:
    def test_defaults(self):
        from openquery.models.intl.who import WhoResult

        r = WhoResult()
        assert r.indicator_code == ""
        assert r.country_code == ""
        assert r.total == 0
        assert r.data_points == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.who import WhoDataPoint, WhoResult

        r = WhoResult(
            indicator_code="WHOSIS_000001",
            country_code="COL",
            total=2,
            data_points=[
                WhoDataPoint(country="COL", year="2020", value="77.1", sex="Both sexes"),
                WhoDataPoint(country="COL", year="2019", value="76.8", sex="Both sexes"),
            ],
        )
        dumped = r.model_dump_json()
        restored = WhoResult.model_validate_json(dumped)
        assert restored.indicator_code == "WHOSIS_000001"
        assert restored.country_code == "COL"
        assert restored.total == 2
        assert len(restored.data_points) == 2
        assert restored.data_points[0].year == "2020"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.who import WhoResult

        r = WhoResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.who import WhoDataPoint

        dp = WhoDataPoint()
        assert dp.country == ""
        assert dp.year == ""
        assert dp.value == ""
        assert dp.sex == ""


# ===========================================================================
# TestWhoSourceMeta
# ===========================================================================


class TestWhoSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.who import WhoSource

        meta = WhoSource().meta()
        assert meta.name == "intl.who"

    def test_meta_country(self):
        from openquery.sources.intl.who import WhoSource

        meta = WhoSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.who import WhoSource

        meta = WhoSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.who import WhoSource

        meta = WhoSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.intl.who import WhoSource

        meta = WhoSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestWhoParseResult
# ===========================================================================

MOCK_WHO_RESPONSE = {
    "value": [
        {
            "Id": 1,
            "IndicatorCode": "WHOSIS_000001",
            "SpatialDim": "COL",
            "TimeDim": 2020,
            "Dim1": "BTSX",
            "NumericValue": 77.1,
            "Value": "77.1 [76.0-78.1]",
        },
        {
            "Id": 2,
            "IndicatorCode": "WHOSIS_000001",
            "SpatialDim": "COL",
            "TimeDim": 2019,
            "Dim1": "BTSX",
            "NumericValue": 76.8,
            "Value": "76.8 [75.7-77.9]",
        },
    ]
}


class TestWhoParseResult:
    def _make_input(self, indicator: str = "WHOSIS_000001", country: str = "COL") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": indicator, "country": country},
        )

    def test_successful_query(self):
        from openquery.sources.intl.who import WhoSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WHO_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WhoSource()
            result = source.query(self._make_input())

        assert result.indicator_code == "WHOSIS_000001"
        assert result.country_code == "COL"
        assert result.total == 2
        assert len(result.data_points) == 2
        assert result.data_points[0].country == "COL"
        assert result.data_points[0].year == "2020"
        assert result.data_points[0].value == "77.1"
        assert result.data_points[0].sex == "BTSX"

    def test_indicator_from_document_number(self):
        from openquery.sources.intl.who import WhoSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WHO_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WhoSource()
            inp = QueryInput(
                document_number="WHOSIS_000001",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.indicator_code == "WHOSIS_000001"

    def test_country_filter_appended_to_params(self):
        from openquery.sources.intl.who import WhoSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"value": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WhoSource()
            source.query(self._make_input())

        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1]["params"]
        assert "$filter" in params
        assert "COL" in params["$filter"]

    def test_no_country_no_filter(self):
        from openquery.sources.intl.who import WhoSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"value": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WhoSource()
            inp = QueryInput(
                document_number="WHOSIS_000001",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            source.query(inp)

        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1]["params"]
        assert "$filter" not in params

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.who import WhoSource

        source = WhoSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="indicator"):
            source.query(inp)

    def test_null_numeric_value(self):
        from openquery.sources.intl.who import WhoSource

        response_with_null = {
            "value": [
                {
                    "IndicatorCode": "WHOSIS_000001",
                    "SpatialDim": "COL",
                    "TimeDim": 2020,
                    "Dim1": "BTSX",
                    "NumericValue": None,
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_with_null
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WhoSource()
            result = source.query(self._make_input())

        assert result.data_points[0].value == ""

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.who import WhoSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WhoSource()
            with pytest.raises(SourceError, match="intl.who"):
                source.query(self._make_input())
