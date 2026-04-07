"""Tests for intl.electricity_maps — carbon intensity of electricity.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIntlElectricityMapsResult — model tests
# ===========================================================================


class TestIntlElectricityMapsResult:
    def test_defaults(self):
        from openquery.models.intl.electricity_maps import IntlElectricityMapsResult

        r = IntlElectricityMapsResult()
        assert r.zone == ""
        assert r.carbon_intensity == ""
        assert r.fossil_fuel_percentage == ""
        assert r.measurement_datetime == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.electricity_maps import IntlElectricityMapsResult

        r = IntlElectricityMapsResult(
            zone="CO",
            carbon_intensity="150",
            fossil_fuel_percentage="45.2",
        )
        dumped = r.model_dump_json()
        restored = IntlElectricityMapsResult.model_validate_json(dumped)
        assert restored.zone == "CO"
        assert restored.carbon_intensity == "150"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.electricity_maps import IntlElectricityMapsResult

        r = IntlElectricityMapsResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestIntlElectricityMapsSourceMeta
# ===========================================================================


class TestIntlElectricityMapsSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        meta = ElectricityMapsSource().meta()
        assert meta.name == "intl.electricity_maps"

    def test_meta_country(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        meta = ElectricityMapsSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        meta = ElectricityMapsSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        meta = ElectricityMapsSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        meta = ElectricityMapsSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestIntlElectricityMapsParseResult
# ===========================================================================

MOCK_EMAPS_RESPONSE = {
    "zone": "CO",
    "carbonIntensity": 150,
    "fossilFuelPercentage": 45.2,
    "datetime": "2024-01-15T12:00:00.000Z",
}


class TestIntlElectricityMapsParseResult:
    def _make_input(self, zone: str = "CO") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"zone": zone},
        )

    def test_no_api_key_raises(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.electricitymaps_api_key = ""
            source = ElectricityMapsSource()
            with pytest.raises(SourceError, match="ELECTRICITYMAPS_API_KEY"):
                source.query(self._make_input())

    def test_missing_zone_raises(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.electricitymaps_api_key = "testkey"
            source = ElectricityMapsSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            with pytest.raises(SourceError, match="zone"):
                source.query(inp)

    def test_successful_query(self):
        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_EMAPS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.electricitymaps_api_key = "testkey"
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__.return_value = mock_client
                mock_client.get.return_value = mock_resp

                source = ElectricityMapsSource()
                result = source.query(self._make_input())

        assert result.zone == "CO"
        assert result.carbon_intensity == "150"
        assert result.fossil_fuel_percentage == "45.2"
        assert "2024" in result.measurement_datetime

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.electricity_maps import ElectricityMapsSource

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )

        with patch("openquery.config.get_settings") as mock_settings:
            mock_settings.return_value.electricitymaps_api_key = "testkey"
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value.__enter__.return_value = mock_client
                mock_client.get.return_value = mock_resp

                source = ElectricityMapsSource()
                with pytest.raises(SourceError, match="intl.electricity_maps"):
                    source.query(self._make_input())
