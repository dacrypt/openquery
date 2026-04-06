"""Tests for intl.imf — IMF DataMapper economic indicators.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestImfResult — model tests
# ===========================================================================


class TestImfResult:
    def test_defaults(self):
        from openquery.models.intl.imf import ImfResult

        r = ImfResult()
        assert r.country_code == ""
        assert r.indicator_code == ""
        assert r.indicator_name == ""
        assert r.data_points == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.imf import ImfDataPoint, ImfResult

        r = ImfResult(
            country_code="COL",
            indicator_code="NGDP_RPCH",
            indicator_name="Real GDP growth",
            data_points=[
                ImfDataPoint(year="2022", value="7.5"),
                ImfDataPoint(year="2021", value="10.9"),
            ],
        )
        dumped = r.model_dump_json()
        restored = ImfResult.model_validate_json(dumped)
        assert restored.country_code == "COL"
        assert restored.indicator_name == "Real GDP growth"
        assert len(restored.data_points) == 2
        assert restored.data_points[0].year == "2022"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.imf import ImfResult

        r = ImfResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.imf import ImfDataPoint

        dp = ImfDataPoint()
        assert dp.year == ""
        assert dp.value == ""


# ===========================================================================
# TestImfSourceMeta
# ===========================================================================


class TestImfSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.imf import ImfSource

        meta = ImfSource().meta()
        assert meta.name == "intl.imf"

    def test_meta_country(self):
        from openquery.sources.intl.imf import ImfSource

        meta = ImfSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.imf import ImfSource

        meta = ImfSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.imf import ImfSource

        meta = ImfSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.intl.imf import ImfSource

        meta = ImfSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestImfParseResult
# ===========================================================================

MOCK_IMF_RESPONSE = {
    "values": {
        "NGDP_RPCH": {
            "COL": {
                "2021": 10.9,
                "2022": 7.5,
            }
        }
    }
}

MOCK_IMF_META_RESPONSE = {
    "indicators": {
        "NGDP_RPCH": {
            "label": "Real GDP growth",
            "description": "Annual percentages of constant price GDP",
        }
    }
}


class TestImfParseResult:
    def _make_input(self, country: str = "COL", indicator: str = "NGDP_RPCH") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "indicator": indicator},
        )

    def _make_mock_client(self, data_response, meta_response=None):
        mock_data_resp = MagicMock()
        mock_data_resp.json.return_value = data_response
        mock_data_resp.status_code = 200
        mock_data_resp.raise_for_status = MagicMock()

        mock_meta_resp = MagicMock()
        mock_meta_resp.json.return_value = meta_response or {}
        mock_meta_resp.status_code = 200 if meta_response else 404

        mock_client = MagicMock()

        def side_effect(url, **kwargs):
            if "indicators" in url:
                return mock_meta_resp
            return mock_data_resp

        mock_client.get.side_effect = side_effect
        return mock_client

    def test_successful_query(self):
        from openquery.sources.intl.imf import ImfSource

        mock_client = self._make_mock_client(MOCK_IMF_RESPONSE, MOCK_IMF_META_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = ImfSource()
            result = source.query(self._make_input())

        assert result.country_code == "COL"
        assert result.indicator_code == "NGDP_RPCH"
        assert result.indicator_name == "Real GDP growth"
        assert len(result.data_points) == 2
        # sorted by year: 2021 first
        assert result.data_points[0].year == "2021"
        assert result.data_points[0].value == "10.9"
        assert result.data_points[1].year == "2022"

    def test_country_uppercased(self):
        from openquery.sources.intl.imf import ImfSource

        mock_client = self._make_mock_client(MOCK_IMF_RESPONSE, MOCK_IMF_META_RESPONSE)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = ImfSource()
            inp = QueryInput(
                document_number="col",
                document_type=DocumentType.CUSTOM,
                extra={"indicator": "NGDP_RPCH"},
            )
            result = source.query(inp)

        assert result.country_code == "COL"

    def test_missing_country_raises(self):
        from openquery.sources.intl.imf import ImfSource

        source = ImfSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": "NGDP_RPCH"},
        )
        with pytest.raises(SourceError, match="country"):
            source.query(inp)

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.imf import ImfSource

        source = ImfSource()
        inp = QueryInput(
            document_number="COL",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="indicator"):
            source.query(inp)

    def test_empty_country_data(self):
        from openquery.sources.intl.imf import ImfSource

        empty_response = {"values": {"NGDP_RPCH": {}}}
        mock_client = self._make_mock_client(empty_response)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = ImfSource()
            result = source.query(self._make_input())

        assert result.data_points == []

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.imf import ImfSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = ImfSource()
            with pytest.raises(SourceError, match="intl.imf"):
                source.query(self._make_input())
