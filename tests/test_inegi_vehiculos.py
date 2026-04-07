"""Tests for mx.inegi_vehiculos — INEGI vehicle registration statistics."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestInegiVehiculosResult — model tests
# ===========================================================================


class TestInegiVehiculosResult:
    def test_defaults(self):
        from openquery.models.mx.inegi_vehiculos import InegiVehiculosResult

        r = InegiVehiculosResult()
        assert r.indicator == ""
        assert r.indicator_name == ""
        assert r.total_observations == 0
        assert r.data_points == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.mx.inegi_vehiculos import InegiVehiculoDataPoint, InegiVehiculosResult

        r = InegiVehiculosResult(
            indicator="6207019014",
            indicator_name="Vehículos registrados",
            total_observations=2,
            data_points=[
                InegiVehiculoDataPoint(period="2023/01", value="1250000"),
                InegiVehiculoDataPoint(period="2023/02", value="1280000"),
            ],
        )
        dumped = r.model_dump_json()
        restored = InegiVehiculosResult.model_validate_json(dumped)
        assert restored.indicator == "6207019014"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.mx.inegi_vehiculos import InegiVehiculosResult

        r = InegiVehiculosResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.mx.inegi_vehiculos import InegiVehiculoDataPoint

        dp = InegiVehiculoDataPoint()
        assert dp.period == ""
        assert dp.value == ""


# ===========================================================================
# TestInegiVehiculosSourceMeta
# ===========================================================================


class TestInegiVehiculosSourceMeta:
    def test_meta_name(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        meta = InegiVehiculosSource().meta()
        assert meta.name == "mx.inegi_vehiculos"

    def test_meta_country(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        meta = InegiVehiculosSource().meta()
        assert meta.country == "MX"

    def test_meta_no_captcha(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        meta = InegiVehiculosSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_supports_custom(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        meta = InegiVehiculosSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestInegiVehiculosParseResult
# ===========================================================================

MOCK_INEGI_RESPONSE = {
    "Series": [
        {
            "INDICADOR": "6207019014",
            "DESC_INDICADOR": "Vehículos de motor registrados en circulación",
            "OBSERVATIONS": [
                {"TIME_PERIOD": "2023/01", "OBS_VALUE": "1250000"},
                {"TIME_PERIOD": "2023/02", "OBS_VALUE": "1280000"},
                {"TIME_PERIOD": "2023/03", "OBS_VALUE": "1310000"},
            ],
        }
    ]
}


class TestInegiVehiculosParseResult:
    def _make_input(self, indicator: str = "6207019014", api_key: str = "test-token") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"indicator": indicator, "api_key": api_key},
        )

    def test_successful_query(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INEGI_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = InegiVehiculosSource()
            result = source.query(self._make_input())

        assert result.indicator == "6207019014"
        assert result.indicator_name == "Vehículos de motor registrados en circulación"
        assert result.total_observations == 3
        assert result.data_points[0].period == "2023/01"
        assert result.data_points[0].value == "1250000"

    def test_missing_api_key_raises(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        source = InegiVehiculosSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="INEGI API key required"):
            source.query(inp)

    def test_empty_series_raises(self):
        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Series": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = InegiVehiculosSource()
            with pytest.raises(SourceError, match="No series data"):
                source.query(self._make_input())

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.mx.inegi_vehiculos import InegiVehiculosSource

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = InegiVehiculosSource()
            with pytest.raises(SourceError, match="mx.inegi_vehiculos"):
                source.query(self._make_input())
