"""Tests for co.runt_estadisticas — RUNT fleet statistics via Socrata API."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestRuntEstadisticasResult — model tests
# ===========================================================================


class TestRuntEstadisticasResult:
    def test_defaults(self):
        from openquery.models.co.runt_estadisticas import RuntEstadisticasResult

        r = RuntEstadisticasResult()
        assert r.search_term == ""
        assert r.total_records == 0
        assert r.total_vehiculos == 0
        assert r.estadisticas == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.runt_estadisticas import RuntEstadistica, RuntEstadisticasResult

        r = RuntEstadisticasResult(
            search_term="TOYOTA",
            total_records=2,
            total_vehiculos=500,
            estadisticas=[
                RuntEstadistica(
                    marca="TOYOTA",
                    clase="AUTOMOVIL",
                    servicio="PARTICULAR",
                    combustible="GASOLINA",
                    departamento="CUNDINAMARCA",
                    cantidad=300,
                ),
                RuntEstadistica(
                    marca="TOYOTA",
                    clase="CAMPERO",
                    servicio="PARTICULAR",
                    combustible="DIESEL",
                    departamento="ANTIOQUIA",
                    cantidad=200,
                ),
            ],
        )
        dumped = r.model_dump_json()
        restored = RuntEstadisticasResult.model_validate_json(dumped)
        assert restored.search_term == "TOYOTA"
        assert len(restored.estadisticas) == 2
        assert restored.estadisticas[0].cantidad == 300

    def test_audit_excluded_from_json(self):
        from openquery.models.co.runt_estadisticas import RuntEstadisticasResult

        r = RuntEstadisticasResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_estadistica_defaults(self):
        from openquery.models.co.runt_estadisticas import RuntEstadistica

        e = RuntEstadistica()
        assert e.marca == ""
        assert e.clase == ""
        assert e.servicio == ""
        assert e.combustible == ""
        assert e.departamento == ""
        assert e.cantidad == 0


# ===========================================================================
# TestRuntEstadisticasSourceMeta
# ===========================================================================


class TestRuntEstadisticasSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        meta = RuntEstadisticasSource().meta()
        assert meta.name == "co.runt_estadisticas"

    def test_meta_country(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        meta = RuntEstadisticasSource().meta()
        assert meta.country == "CO"

    def test_meta_no_captcha(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        meta = RuntEstadisticasSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        meta = RuntEstadisticasSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        meta = RuntEstadisticasSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestRuntEstadisticasParseResult
# ===========================================================================

MOCK_SOCRATA_RESPONSE = [
    {
        "marca": "TOYOTA",
        "clase": "AUTOMOVIL",
        "servicio": "PARTICULAR",
        "combustible": "GASOLINA",
        "departamento": "CUNDINAMARCA",
        "cantidad": "1500",
    },
    {
        "marca": "TOYOTA",
        "clase": "CAMPERO",
        "servicio": "PARTICULAR",
        "combustible": "DIESEL",
        "departamento": "ANTIOQUIA",
        "cantidad": "800",
    },
]


class TestRuntEstadisticasParseResult:
    def _make_input(self, marca: str = "TOYOTA") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"marca": marca},
        )

    def test_successful_query(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SOCRATA_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = RuntEstadisticasSource()
            result = source.query(self._make_input())

        assert result.total_records == 2
        assert result.total_vehiculos == 2300
        assert result.estadisticas[0].marca == "TOYOTA"
        assert result.estadisticas[0].cantidad == 1500

    def test_empty_response(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = RuntEstadisticasSource()
            result = source.query(self._make_input())

        assert result.total_records == 0
        assert result.total_vehiculos == 0
        assert result.estadisticas == []

    def test_multiple_filters(self):
        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SOCRATA_RESPONSE[:1]
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = RuntEstadisticasSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"marca": "TOYOTA", "clase": "AUTOMOVIL", "departamento": "CUNDINAMARCA"},
            )
            result = source.query(inp)

        assert result.total_records == 1

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.co.runt_estadisticas import RuntEstadisticasSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = RuntEstadisticasSource()
            with pytest.raises(SourceError, match="co.runt_estadisticas"):
                source.query(self._make_input())
