"""Tests for intl.ocm — Open Charge Map EV charging stations.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestOcmResult — model tests
# ===========================================================================


class TestOcmResult:
    def test_defaults(self):
        from openquery.models.intl.ocm import OcmResult

        r = OcmResult()
        assert r.search_params == ""
        assert r.total_stations == 0
        assert r.stations == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.ocm import OcmConnector, OcmResult, OcmStation

        r = OcmResult(
            search_params="country=DE",
            total_stations=1,
            stations=[
                OcmStation(
                    name="Berlin Fast Charger",
                    operator="IONITY",
                    city="Berlin",
                    country="DE",
                    latitude=52.52,
                    longitude=13.405,
                    connectors=[OcmConnector(connector_type="CCS", power_kw=150.0)],
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = OcmResult.model_validate_json(dumped)
        assert restored.total_stations == 1
        assert restored.stations[0].name == "Berlin Fast Charger"
        assert restored.stations[0].connectors[0].connector_type == "CCS"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.ocm import OcmResult

        r = OcmResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_connector_defaults(self):
        from openquery.models.intl.ocm import OcmConnector

        c = OcmConnector()
        assert c.connector_type == ""
        assert c.power_kw == 0.0
        assert c.voltage == 0
        assert c.amps == 0
        assert c.current_type == ""

    def test_station_defaults(self):
        from openquery.models.intl.ocm import OcmStation

        s = OcmStation()
        assert s.name == ""
        assert s.connectors == []
        assert s.num_points == 0


# ===========================================================================
# TestOcmSourceMeta
# ===========================================================================


class TestOcmSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.ocm import OcmSource

        assert OcmSource().meta().name == "intl.ocm"

    def test_meta_country(self):
        from openquery.sources.intl.ocm import OcmSource

        assert OcmSource().meta().country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.ocm import OcmSource

        meta = OcmSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.ocm import OcmSource

        assert OcmSource().meta().rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.intl.ocm import OcmSource

        assert DocumentType.CUSTOM in OcmSource().meta().supported_inputs


# ===========================================================================
# TestOcmParseResult
# ===========================================================================

MOCK_OCM_RESPONSE = [
    {
        "AddressInfo": {
            "Title": "Test Station",
            "AddressLine1": "123 Main St",
            "Town": "Amsterdam",
            "Country": {"ISOCode": "NL"},
            "Latitude": 52.37,
            "Longitude": 4.89,
        },
        "OperatorInfo": {"Title": "EV Operator NL"},
        "StatusType": {"Title": "Operational"},
        "UsageType": {"Title": "Public"},
        "NumberOfPoints": 4,
        "Connections": [
            {
                "ConnectionType": {"Title": "CCS (Type 2)"},
                "PowerKW": 50.0,
                "Voltage": 400,
                "Amps": 125,
                "Level": {"Title": "DC Fast"},
            }
        ],
    }
]


class TestOcmParseResult:
    def _make_input(self, country: str = "NL") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country},
        )

    def test_successful_query(self):
        from openquery.sources.intl.ocm import OcmSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OCM_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = OcmSource().query(self._make_input())

        assert result.total_stations == 1
        assert result.stations[0].name == "Test Station"
        assert result.stations[0].city == "Amsterdam"
        assert result.stations[0].operator == "EV Operator NL"
        assert result.stations[0].num_points == 4
        assert len(result.stations[0].connectors) == 1
        assert result.stations[0].connectors[0].connector_type == "CCS (Type 2)"
        assert result.stations[0].connectors[0].power_kw == 50.0

    def test_missing_country_and_location_raises(self):
        from openquery.sources.intl.ocm import OcmSource

        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="intl.ocm"):
            OcmSource().query(inp)

    def test_radius_search_params(self):
        from openquery.sources.intl.ocm import OcmSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"latitude": "52.37", "longitude": "4.89", "distance": "10"},
            )
            result = OcmSource().query(inp)

        assert "lat=52.37" in result.search_params

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.ocm import OcmSource

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="intl.ocm"):
                OcmSource().query(self._make_input())

    def test_empty_response(self):
        from openquery.sources.intl.ocm import OcmSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = OcmSource().query(self._make_input())

        assert result.total_stations == 0
        assert result.stations == []
