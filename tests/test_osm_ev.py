"""Tests for intl.osm_ev — OpenStreetMap EV charging stations (Overpass).

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestOsmEvResult — model tests
# ===========================================================================


class TestOsmEvResult:
    def test_defaults(self):
        from openquery.models.intl.osm_ev import OsmEvResult

        r = OsmEvResult()
        assert r.search_params == ""
        assert r.total_stations == 0
        assert r.stations == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.osm_ev import OsmEvResult, OsmEvStation

        r = OsmEvResult(
            search_params="country=FR",
            total_stations=1,
            stations=[
                OsmEvStation(
                    osm_id=12345678,
                    latitude=48.8566,
                    longitude=2.3522,
                    operator="Ionity",
                    capacity="4",
                    socket_types=["socket:ccs", "socket:chademo"],
                    fee="yes",
                    opening_hours="24/7",
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = OsmEvResult.model_validate_json(dumped)
        assert restored.total_stations == 1
        assert restored.stations[0].osm_id == 12345678
        assert restored.stations[0].socket_types == ["socket:ccs", "socket:chademo"]

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.osm_ev import OsmEvResult

        r = OsmEvResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_station_defaults(self):
        from openquery.models.intl.osm_ev import OsmEvStation

        s = OsmEvStation()
        assert s.osm_id == 0
        assert s.socket_types == []
        assert s.operator == ""
        assert s.fee == ""


# ===========================================================================
# TestOsmEvSourceMeta
# ===========================================================================


class TestOsmEvSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        assert OsmEvSource().meta().name == "intl.osm_ev"

    def test_meta_country(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        assert OsmEvSource().meta().country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        meta = OsmEvSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        assert OsmEvSource().meta().rate_limit_rpm == 5

    def test_meta_supports_custom(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        assert DocumentType.CUSTOM in OsmEvSource().meta().supported_inputs


# ===========================================================================
# TestOsmEvParseResult
# ===========================================================================

MOCK_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 987654321,
            "lat": 48.8566,
            "lon": 2.3522,
            "tags": {
                "amenity": "charging_station",
                "operator": "Total Energies",
                "capacity": "2",
                "socket:type2": "yes",
                "socket:ccs": "yes",
                "fee": "yes",
                "opening_hours": "Mo-Su 00:00-24:00",
            },
        },
        {
            "type": "node",
            "id": 111222333,
            "lat": 48.9000,
            "lon": 2.4000,
            "tags": {
                "amenity": "charging_station",
                "operator": "Ionity",
                "socket:tesla_supercharger": "yes",
            },
        },
        # Non-node element — should be skipped
        {
            "type": "way",
            "id": 999,
            "tags": {"amenity": "charging_station"},
        },
    ]
}


class TestOsmEvParseResult:
    def _make_input(self, country: str = "FR") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country},
        )

    def test_successful_query(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OVERPASS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            result = OsmEvSource().query(self._make_input())

        # way element skipped — only 2 nodes
        assert result.total_stations == 2
        assert result.stations[0].osm_id == 987654321
        assert result.stations[0].operator == "Total Energies"
        assert result.stations[0].capacity == "2"
        assert "socket:type2" in result.stations[0].socket_types
        assert "socket:ccs" in result.stations[0].socket_types
        assert result.stations[0].fee == "yes"
        assert result.stations[0].opening_hours == "Mo-Su 00:00-24:00"

    def test_missing_country_and_location_raises(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="intl.osm_ev"):
            OsmEvSource().query(inp)

    def test_radius_search_uses_post(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"elements": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"latitude": "48.8566", "longitude": "2.3522", "radius": "1000"},
            )
            result = OsmEvSource().query(inp)

        assert "lat=48.8566" in result.search_params
        mock_client.post.assert_called_once()

    def test_country_query_uses_area_filter(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        source = OsmEvSource()
        query = source._build_query("DE", "", "", "")
        assert 'area["ISO3166-1"="DE"]' in query
        assert "charging_station" in query

    def test_radius_query_uses_around(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        source = OsmEvSource()
        query = source._build_query("", "52.52", "13.405", "2000")
        assert "around:2000" in query
        assert "charging_station" in query

    def test_socket_no_tag_excluded(self):
        from openquery.sources.intl.osm_ev import OsmEvSource

        resp_with_no = {
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": 1.0,
                    "lon": 1.0,
                    "tags": {
                        "socket:type2": "no",
                        "socket:ccs": "yes",
                    },
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = resp_with_no
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            result = OsmEvSource().query(self._make_input())

        assert "socket:type2" not in result.stations[0].socket_types
        assert "socket:ccs" in result.stations[0].socket_types

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.osm_ev import OsmEvSource

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            with pytest.raises(SourceError, match="intl.osm_ev"):
                OsmEvSource().query(self._make_input())
