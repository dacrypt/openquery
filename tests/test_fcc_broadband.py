"""Tests for us.fcc_broadband — FCC National Broadband Map.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestFccBroadbandResult — model tests
# ===========================================================================


class TestFccBroadbandResult:
    def test_defaults(self):
        from openquery.models.us.fcc_broadband import FccBroadbandResult

        r = FccBroadbandResult()
        assert r.location == ""
        assert r.providers == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.fcc_broadband import FccBroadbandResult, FccProvider

        r = FccBroadbandResult(
            location="123 Main St, Anytown, CA",
            providers=[
                FccProvider(name="Comcast", technology="Cable", speed="200/20 Mbps"),
                FccProvider(name="AT&T", technology="Fiber", speed="1000/1000 Mbps"),
            ],
        )
        dumped = r.model_dump_json()
        restored = FccBroadbandResult.model_validate_json(dumped)
        assert restored.location == "123 Main St, Anytown, CA"
        assert len(restored.providers) == 2
        assert restored.providers[0].name == "Comcast"

    def test_audit_excluded_from_json(self):
        from openquery.models.us.fcc_broadband import FccBroadbandResult

        r = FccBroadbandResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_provider_defaults(self):
        from openquery.models.us.fcc_broadband import FccProvider

        p = FccProvider()
        assert p.name == ""
        assert p.technology == ""
        assert p.speed == ""


# ===========================================================================
# TestFccBroadbandSourceMeta
# ===========================================================================


class TestFccBroadbandSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        meta = FccBroadbandSource().meta()
        assert meta.name == "us.fcc_broadband"

    def test_meta_country(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        meta = FccBroadbandSource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        meta = FccBroadbandSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        meta = FccBroadbandSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        meta = FccBroadbandSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestFccBroadbandParseResult
# ===========================================================================

MOCK_FCC_RESPONSE = {
    "availability": [
        {
            "brand_name": "Comcast",
            "technology": 40,
            "max_advertised_download_speed": 200,
            "max_advertised_upload_speed": 20,
        },
        {
            "brand_name": "AT&T",
            "technology": 50,
            "max_advertised_download_speed": 1000,
            "max_advertised_upload_speed": 1000,
        },
    ]
}


class TestFccBroadbandParseResult:
    def _make_input(self, location: str = "123 Main St, Anytown, CA") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"location": location},
        )

    def test_successful_query(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_FCC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FccBroadbandSource()
            result = source.query(self._make_input())

        assert result.location == "123 Main St, Anytown, CA"
        assert len(result.providers) == 2
        assert result.providers[0].name == "Comcast"
        assert result.providers[0].technology == "Cable"
        assert "200" in result.providers[0].speed
        assert result.providers[1].technology == "Fiber"

    def test_missing_location_raises(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        source = FccBroadbandSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="location"):
            source.query(inp)

    def test_coordinates_accepted(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_FCC_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FccBroadbandSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"latitude": "37.7749", "longitude": "-122.4194"},
            )
            result = source.query(inp)

        assert len(result.providers) == 2

    def test_empty_availability_returns_empty_providers(self):
        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"availability": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FccBroadbandSource()
            result = source.query(self._make_input())

        assert result.providers == []
        assert "No broadband" in result.details

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.fcc_broadband import FccBroadbandSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = FccBroadbandSource()
            with pytest.raises(SourceError, match="us.fcc_broadband"):
                source.query(self._make_input())
