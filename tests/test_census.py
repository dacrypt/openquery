"""Tests for us.census — US Census Bureau ACS data.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestCensusResult — model tests
# ===========================================================================


class TestCensusResult:
    def test_defaults(self):
        from openquery.models.us.census import CensusResult

        r = CensusResult()
        assert r.geography == ""
        assert r.variable == ""
        assert r.value == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.census import CensusResult

        r = CensusResult(
            geography="California",
            variable="B01003_001E",
            value="39538223",
            details="Total Population",
        )
        dumped = r.model_dump_json()
        restored = CensusResult.model_validate_json(dumped)
        assert restored.geography == "California"
        assert restored.variable == "B01003_001E"
        assert restored.value == "39538223"

    def test_audit_excluded_from_json(self):
        from openquery.models.us.census import CensusResult

        r = CensusResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestCensusSourceMeta
# ===========================================================================


class TestCensusSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.census import CensusSource

        meta = CensusSource().meta()
        assert meta.name == "us.census"

    def test_meta_country(self):
        from openquery.sources.us.census import CensusSource

        meta = CensusSource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.census import CensusSource

        meta = CensusSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.census import CensusSource

        meta = CensusSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.census import CensusSource

        meta = CensusSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestCensusParseResult
# ===========================================================================

MOCK_CENSUS_RESPONSE = [
    ["NAME", "B01003_001E", "state"],
    ["California", "39538223", "06"],
]


class TestCensusParseResult:
    def _make_input(self, geography: str = "06", variable: str = "B01003_001E") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"geography": geography, "variable": variable},
        )

    def test_successful_query(self):
        from openquery.sources.us.census import CensusSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_CENSUS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CensusSource()
            result = source.query(self._make_input())

        assert result.geography == "California"
        assert result.variable == "B01003_001E"
        assert result.value == "39538223"
        assert result.details == "Total Population"

    def test_missing_geography_raises(self):
        from openquery.sources.us.census import CensusSource

        source = CensusSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"variable": "B01003_001E"},
        )
        with pytest.raises(SourceError, match="state FIPS"):
            source.query(inp)

    def test_geography_from_document_number(self):
        from openquery.sources.us.census import CensusSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_CENSUS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CensusSource()
            inp = QueryInput(
                document_number="06",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.value == "39538223"

    def test_state_colon_format_preserved(self):
        from openquery.sources.us.census import CensusSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_CENSUS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CensusSource()
            # "state:06" format should be passed through unchanged
            result = source.query(self._make_input(geography="state:06"))

        assert result.value == "39538223"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.census import CensusSource

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CensusSource()
            with pytest.raises(SourceError, match="us.census"):
                source.query(self._make_input())
