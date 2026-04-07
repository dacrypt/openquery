"""Tests for co.estaciones_ev_epm — EPM EV charging stations (Colombia).

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestEstacionesEvEpmResult — model tests
# ===========================================================================


class TestEstacionesEvEpmResult:
    def test_defaults(self):
        from openquery.models.co.estaciones_ev_epm import EstacionesEvEpmResult

        r = EstacionesEvEpmResult()
        assert r.search_params == ""
        assert r.total_stations == 0
        assert r.stations == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.estaciones_ev_epm import EpmStation, EstacionesEvEpmResult

        r = EstacionesEvEpmResult(
            search_params="ciudad=Medellín",
            total_stations=1,
            stations=[
                EpmStation(
                    nombre="EPM El Poblado",
                    direccion="Calle 10 #43D-28",
                    ciudad="Medellín",
                    departamento="Antioquia",
                    tipo="Eléctrico",
                    latitud=6.2089,
                    longitud=-75.5676,
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = EstacionesEvEpmResult.model_validate_json(dumped)
        assert restored.total_stations == 1
        assert restored.stations[0].nombre == "EPM El Poblado"
        assert restored.stations[0].ciudad == "Medellín"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.estaciones_ev_epm import EstacionesEvEpmResult

        r = EstacionesEvEpmResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_station_defaults(self):
        from openquery.models.co.estaciones_ev_epm import EpmStation

        s = EpmStation()
        assert s.nombre == ""
        assert s.latitud == 0.0
        assert s.longitud == 0.0


# ===========================================================================
# TestEstacionesEvEpmSourceMeta
# ===========================================================================


class TestEstacionesEvEpmSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        assert EstacionesEvEpmSource().meta().name == "co.estaciones_ev_epm"

    def test_meta_country(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        assert EstacionesEvEpmSource().meta().country == "CO"

    def test_meta_no_captcha(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        meta = EstacionesEvEpmSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        assert EstacionesEvEpmSource().meta().rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        assert DocumentType.CUSTOM in EstacionesEvEpmSource().meta().supported_inputs


# ===========================================================================
# TestEstacionesEvEpmParseResult
# ===========================================================================

MOCK_EPM_RESPONSE = [
    {
        "nombre": "EPM Laureles",
        "direccion": "Carrera 76 #40-12",
        "ciudad": "Medellín",
        "departamento": "Antioquia",
        "tipo": "Eléctrico",
        "latitud": "6.2500",
        "longitud": "-75.5900",
    },
    {
        "nombre": "EPM Centro",
        "direccion": "Calle 55 #45-23",
        "ciudad": "Medellín",
        "departamento": "Antioquia",
        "tipo": "Gas Natural",
        "latitud": "6.2518",
        "longitud": "-75.5636",
    },
]


class TestEstacionesEvEpmParseResult:
    def _make_input(self, ciudad: str = "Medellín") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"ciudad": ciudad},
        )

    def test_successful_query(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_EPM_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = EstacionesEvEpmSource().query(self._make_input())

        assert result.total_stations == 2
        assert result.stations[0].nombre == "EPM Laureles"
        assert result.stations[0].latitud == 6.25
        assert result.stations[1].tipo == "Gas Natural"

    def test_no_filters_returns_all(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

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
                extra={},
            )
            result = EstacionesEvEpmSource().query(inp)

        assert result.search_params == "all"

    def test_invalid_lat_lon_defaults_to_zero(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        bad_data = [{"nombre": "X", "latitud": "invalid", "longitud": None}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = bad_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = EstacionesEvEpmSource().query(self._make_input())

        assert result.stations[0].latitud == 0.0
        assert result.stations[0].longitud == 0.0

    def test_departamento_filter(self):
        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

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
                extra={"departamento": "Antioquia"},
            )
            result = EstacionesEvEpmSource().query(inp)

        assert "departamento=Antioquia" in result.search_params

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.co.estaciones_ev_epm import EstacionesEvEpmSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="co.estaciones_ev_epm"):
                EstacionesEvEpmSource().query(self._make_input())
