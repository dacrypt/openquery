"""Tests for us.afdc — DOE Alternative Fuels Station Locator.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestAfdcResult — model tests
# ===========================================================================


class TestAfdcResult:
    def test_defaults(self):
        from openquery.models.us.afdc import AfdcResult

        r = AfdcResult()
        assert r.search_params == ""
        assert r.total_stations == 0
        assert r.stations == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.afdc import AfdcResult, AfdcStation

        r = AfdcResult(
            search_params="state=CA",
            total_stations=1,
            stations=[
                AfdcStation(
                    name="Tesla Supercharger",
                    street="1 Infinite Loop",
                    city="Cupertino",
                    state="CA",
                    zip="95014",
                    ev_network="Tesla",
                    ev_connector_types=["TESLA"],
                    ev_dc_fast_count=8,
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = AfdcResult.model_validate_json(dumped)
        assert restored.total_stations == 1
        assert restored.stations[0].name == "Tesla Supercharger"
        assert restored.stations[0].ev_connector_types == ["TESLA"]

    def test_audit_excluded_from_json(self):
        from openquery.models.us.afdc import AfdcResult

        r = AfdcResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_station_defaults(self):
        from openquery.models.us.afdc import AfdcStation

        s = AfdcStation()
        assert s.name == ""
        assert s.ev_connector_types == []
        assert s.ev_level2_count == 0
        assert s.ev_dc_fast_count == 0


# ===========================================================================
# TestAfdcSourceMeta
# ===========================================================================


class TestAfdcSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.afdc import AfdcSource

        assert AfdcSource().meta().name == "us.afdc"

    def test_meta_country(self):
        from openquery.sources.us.afdc import AfdcSource

        assert AfdcSource().meta().country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.afdc import AfdcSource

        meta = AfdcSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.afdc import AfdcSource

        assert AfdcSource().meta().rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.afdc import AfdcSource

        assert DocumentType.CUSTOM in AfdcSource().meta().supported_inputs


# ===========================================================================
# TestAfdcParseResult
# ===========================================================================

MOCK_AFDC_RESPONSE = {
    "total_results": 2,
    "fuel_stations": [
        {
            "station_name": "ChargePoint Station",
            "street_address": "500 Howard St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "latitude": 37.7879,
            "longitude": -122.3966,
            "ev_network": "ChargePoint Network",
            "ev_connector_types": ["J1772"],
            "ev_level2_evse_num": 4,
            "ev_dc_fast_num": None,
            "ev_pricing": "Free",
            "status_code": "E",
        },
        {
            "station_name": "Electrify America",
            "street_address": "1000 Market St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102",
            "latitude": 37.7786,
            "longitude": -122.4138,
            "ev_network": "Electrify America",
            "ev_connector_types": ["CCS", "CHAdeMO"],
            "ev_level2_evse_num": 0,
            "ev_dc_fast_num": 6,
            "ev_pricing": None,
            "status_code": "E",
        },
    ],
}


class TestAfdcParseResult:
    def _make_input(self, state: str = "CA") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"state": state},
        )

    def test_successful_query(self):
        from openquery.sources.us.afdc import AfdcSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_AFDC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = AfdcSource().query(self._make_input())

        assert result.total_stations == 2
        assert len(result.stations) == 2
        assert result.stations[0].name == "ChargePoint Station"
        assert result.stations[0].ev_level2_count == 4
        assert result.stations[1].ev_connector_types == ["CCS", "CHAdeMO"]
        assert result.stations[1].ev_dc_fast_count == 6

    def test_missing_filters_raises(self):
        from openquery.sources.us.afdc import AfdcSource

        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="us.afdc"):
            AfdcSource().query(inp)

    def test_zip_filter(self):
        from openquery.sources.us.afdc import AfdcSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"total_results": 0, "fuel_stations": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"zip": "94105"},
            )
            result = AfdcSource().query(inp)

        assert "zip=94105" in result.search_params

    def test_null_counts_default_to_zero(self):
        from openquery.sources.us.afdc import AfdcSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_AFDC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = AfdcSource().query(self._make_input())

        # ev_dc_fast_num was None for first station
        assert result.stations[0].ev_dc_fast_count == 0

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.afdc import AfdcSource

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="us.afdc"):
                AfdcSource().query(self._make_input())
