"""Tests for intl.fuel_prices — World Bank global fuel prices.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIntlFuelPricesResult — model tests
# ===========================================================================


class TestIntlFuelPricesResult:
    def test_defaults(self):
        from openquery.models.intl.fuel_prices import IntlFuelPricesResult

        r = IntlFuelPricesResult()
        assert r.country_code == ""
        assert r.fuel_type == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.fuel_prices import FuelPriceDataPoint, IntlFuelPricesResult

        r = IntlFuelPricesResult(
            country_code="CO",
            fuel_type="gasoline",
            data_points=[FuelPriceDataPoint(date="2022", price="1.45", currency="USD")],
        )
        dumped = r.model_dump_json()
        restored = IntlFuelPricesResult.model_validate_json(dumped)
        assert restored.country_code == "CO"
        assert len(restored.data_points) == 1
        assert restored.data_points[0].date == "2022"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.fuel_prices import IntlFuelPricesResult

        r = IntlFuelPricesResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.fuel_prices import FuelPriceDataPoint

        dp = FuelPriceDataPoint()
        assert dp.date == ""
        assert dp.price == ""
        assert dp.currency == "USD"


# ===========================================================================
# TestIntlFuelPricesSourceMeta
# ===========================================================================


class TestIntlFuelPricesSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        meta = FuelPricesSource().meta()
        assert meta.name == "intl.fuel_prices"

    def test_meta_country(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        meta = FuelPricesSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        meta = FuelPricesSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        meta = FuelPricesSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        meta = FuelPricesSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestIntlFuelPricesParseResult
# ===========================================================================

MOCK_WB_RESPONSE = [
    {"page": 1, "pages": 1, "per_page": 50, "total": 2},
    [
        {
            "indicator": {"id": "EP.PMP.SGAS.CD", "value": "Pump price for gasoline"},
            "country": {"id": "CO", "value": "Colombia"},
            "date": "2022",
            "value": 1.45,
        },
        {
            "indicator": {"id": "EP.PMP.SGAS.CD", "value": "Pump price for gasoline"},
            "country": {"id": "CO", "value": "Colombia"},
            "date": "2021",
            "value": 1.38,
        },
    ],
]


class TestIntlFuelPricesParseResult:
    def _make_input(self, country: str = "CO", fuel_type: str = "gasoline") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "fuel_type": fuel_type},
        )

    def test_successful_query(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WB_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FuelPricesSource()
            result = source.query(self._make_input())

        assert result.country_code == "CO"
        assert result.fuel_type == "gasoline"
        assert len(result.data_points) == 2
        assert result.data_points[0].date == "2022"
        assert "1.45" in result.data_points[0].price

    def test_missing_country_raises(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        source = FuelPricesSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"fuel_type": "gasoline"},
        )
        with pytest.raises(SourceError, match="country"):
            source.query(inp)

    def test_country_from_document_number(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_WB_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FuelPricesSource()
            inp = QueryInput(
                document_number="co",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.country_code == "CO"

    def test_null_value_records(self):
        from openquery.sources.intl.fuel_prices import FuelPricesSource

        response_with_null = [
            {"page": 1, "pages": 1, "per_page": 50, "total": 1},
            [{"indicator": {}, "country": {}, "date": "2023", "value": None}],
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_with_null
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FuelPricesSource()
            result = source.query(self._make_input())

        assert result.data_points[0].price == ""

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.fuel_prices import FuelPricesSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FuelPricesSource()
            with pytest.raises(SourceError, match="intl.fuel_prices"):
                source.query(self._make_input())
