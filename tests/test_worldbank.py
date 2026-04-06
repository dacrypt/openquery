"""Tests for intl.worldbank — World Bank country indicators.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestWorldBankResult — model tests
# ===========================================================================


class TestWorldBankResult:
    def test_defaults(self):
        from openquery.models.intl.worldbank import WorldBankResult

        r = WorldBankResult()
        assert r.country_code == ""
        assert r.country_name == ""
        assert r.indicator_code == ""
        assert r.indicator_name == ""
        assert r.data_points == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.worldbank import WorldBankDataPoint, WorldBankResult

        r = WorldBankResult(
            country_code="CO",
            country_name="Colombia",
            indicator_code="NY.GDP.MKTP.CD",
            indicator_name="GDP (current US$)",
            data_points=[
                WorldBankDataPoint(year="2022", value="343652000000"),
                WorldBankDataPoint(year="2021", value="314457000000"),
            ],
        )
        dumped = r.model_dump_json()
        restored = WorldBankResult.model_validate_json(dumped)
        assert restored.country_code == "CO"
        assert restored.indicator_name == "GDP (current US$)"
        assert len(restored.data_points) == 2
        assert restored.data_points[0].year == "2022"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.worldbank import WorldBankResult

        r = WorldBankResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.worldbank import WorldBankDataPoint

        dp = WorldBankDataPoint()
        assert dp.year == ""
        assert dp.value == ""


# ===========================================================================
# TestWorldBankSourceMeta
# ===========================================================================


class TestWorldBankSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        meta = WorldBankSource().meta()
        assert meta.name == "intl.worldbank"

    def test_meta_country(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        meta = WorldBankSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        meta = WorldBankSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        meta = WorldBankSource().meta()
        assert meta.rate_limit_rpm == 30

    def test_meta_supports_custom(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        meta = WorldBankSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestWorldBankParseResult
# ===========================================================================

MOCK_WORLDBANK_RESPONSE = [
    {
        "page": 1,
        "pages": 1,
        "per_page": 50,
        "total": 2,
    },
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
            "value": 314457000000.0,
        },
    ],
]


class TestWorldBankParseResult:
    def _make_input(self, country: str = "CO", indicator: str = "NY.GDP.MKTP.CD") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "indicator": indicator},
        )

    def test_successful_query(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WORLDBANK_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WorldBankSource()
            result = source.query(self._make_input())

        assert result.country_code == "CO"
        assert result.country_name == "Colombia"
        assert result.indicator_code == "NY.GDP.MKTP.CD"
        assert result.indicator_name == "GDP (current US$)"
        assert len(result.data_points) == 2
        assert result.data_points[0].year == "2022"
        assert "343652000000" in result.data_points[0].value

    def test_missing_country_raises(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        source = WorldBankSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": "NY.GDP.MKTP.CD"},
        )
        with pytest.raises(SourceError, match="country"):
            source.query(inp)

    def test_missing_indicator_raises(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        source = WorldBankSource()
        inp = QueryInput(
            document_number="CO",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="indicator"):
            source.query(inp)

    def test_country_from_document_number(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WORLDBANK_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WorldBankSource()
            inp = QueryInput(
                document_number="co",
                document_type=DocumentType.CUSTOM,
                extra={"indicator": "NY.GDP.MKTP.CD"},
            )
            result = source.query(inp)

        # country code should be uppercased
        assert result.country_code == "CO"

    def test_null_value_records(self):
        from openquery.sources.intl.worldbank import WorldBankSource

        response_with_null = [
            {"page": 1, "pages": 1, "per_page": 50, "total": 1},
            [
                {
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                    "country": {"id": "CO", "value": "Colombia"},
                    "date": "2023",
                    "value": None,
                }
            ],
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_with_null
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WorldBankSource()
            result = source.query(self._make_input())

        assert result.data_points[0].value == ""

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.worldbank import WorldBankSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = WorldBankSource()
            with pytest.raises(SourceError, match="intl.worldbank"):
                source.query(self._make_input())
