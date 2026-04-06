"""Tests for intl.wdi — World Development Indicators."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

MOCK_WDI_RESPONSE = [
    {"page": 1, "pages": 1, "per_page": 50, "total": 2},
    [
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
            "country": {"id": "CO", "value": "Colombia"},
            "date": "2022",
            "value": 343652000000.0,
        },
        {
            "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
            "country": {"id": "CO", "value": "Colombia"},
            "date": "2021",
            "value": None,
        },
    ],
]


class TestWdiResult:
    def test_defaults(self):
        from openquery.models.intl.wdi import WdiResult

        r = WdiResult()
        assert r.country_code == ""
        assert r.indicator == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.wdi import WdiDataPoint, WdiResult

        r = WdiResult(
            country_code="CO",
            indicator="NY.GDP.MKTP.CD",
            data_points=[WdiDataPoint(year="2022", value="343652000000")],
        )
        dumped = r.model_dump_json()
        restored = WdiResult.model_validate_json(dumped)
        assert restored.country_code == "CO"
        assert len(restored.data_points) == 1

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.wdi import WdiResult

        r = WdiResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()

    def test_data_point_defaults(self):
        from openquery.models.intl.wdi import WdiDataPoint

        dp = WdiDataPoint()
        assert dp.year == ""
        assert dp.value == ""


class TestWdiSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.wdi import WdiSource

        assert WdiSource().meta().name == "intl.wdi"

    def test_meta_country(self):
        from openquery.sources.intl.wdi import WdiSource

        assert WdiSource().meta().country == "INTL"

    def test_meta_no_browser(self):
        from openquery.sources.intl.wdi import WdiSource

        meta = WdiSource().meta()
        assert meta.requires_browser is False
        assert meta.requires_captcha is False

    def test_meta_supports_custom(self):
        from openquery.sources.intl.wdi import WdiSource

        assert DocumentType.CUSTOM in WdiSource().meta().supported_inputs


class TestWdiParseResult:
    def _make_input(self, country: str = "CO", indicator: str = "NY.GDP.MKTP.CD") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "indicator": indicator},
        )

    def test_missing_country_raises(self):
        from openquery.sources.intl.wdi import WdiSource

        with pytest.raises(SourceError, match="country"):
            WdiSource().query(
                QueryInput(
                    document_number="",
                    document_type=DocumentType.CUSTOM,
                    extra={"indicator": "NY.GDP.MKTP.CD"},
                )
            )

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.wdi import WdiSource

        with pytest.raises(SourceError, match="indicator"):
            WdiSource().query(
                QueryInput(
                    document_number="CO",
                    document_type=DocumentType.CUSTOM,
                    extra={},
                )
            )

    def test_successful_query(self):
        from openquery.sources.intl.wdi import WdiSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WDI_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = WdiSource().query(self._make_input())

        assert result.country_code == "CO"
        assert result.indicator == "NY.GDP.MKTP.CD"
        assert len(result.data_points) == 2
        assert result.data_points[0].year == "2022"
        assert "343652000000" in result.data_points[0].value

    def test_null_value_becomes_empty_string(self):
        from openquery.sources.intl.wdi import WdiSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WDI_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = WdiSource().query(self._make_input())

        assert result.data_points[1].value == ""

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.wdi import WdiSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="intl.wdi"):
                WdiSource().query(self._make_input())
