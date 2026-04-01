"""Tests for all Socrata API sources — mocked httpx responses.

Covers: vehiculos, peajes, combustible, estaciones_ev, siniestralidad.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_httpx_response(json_data, status_code=200):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp
        )
    return resp


def _mock_client(response):
    """Create a mock httpx.Client context manager."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = response
    return client


def _custom_input(**extra):
    return QueryInput(
        document_type=DocumentType.CUSTOM,
        document_number="",
        extra=extra,
    )


def _plate_input(plate):
    return QueryInput(
        document_type=DocumentType.PLATE,
        document_number=plate,
    )


# ===========================================================================
# co.vehiculos
# ===========================================================================

class TestVehiculosSource:
    @patch("httpx.Client")
    def test_query_by_plate(self, mock_client_cls):
        from openquery.sources.co.vehiculos import VehiculosSource

        data = [{
            "placa": "ABC123",
            "clase": "AUTOMOVIL",
            "marca": "CHEVROLET",
            "modelo": "2020",
            "servicio": "PARTICULAR",
            "cilindraje": "1500",
        }]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = VehiculosSource()
        result = src.query(_plate_input("abc123"))
        assert result.placa == "ABC123"
        assert result.marca == "CHEVROLET"
        assert result.total == 1

    @patch("httpx.Client")
    def test_query_by_brand(self, mock_client_cls):
        from openquery.sources.co.vehiculos import VehiculosSource

        data = [
            {"placa": "AAA111", "marca": "RENAULT", "modelo": "2019"},
            {"placa": "BBB222", "marca": "RENAULT", "modelo": "2021"},
        ]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = VehiculosSource()
        result = src.query(_custom_input(marca="renault"))
        assert result.marca == "RENAULT"
        assert result.total == 2

    @patch("httpx.Client")
    def test_query_by_plate_not_found(self, mock_client_cls):
        from openquery.sources.co.vehiculos import VehiculosSource

        mock_client_cls.return_value = _mock_client(_mock_httpx_response([]))

        src = VehiculosSource()
        result = src.query(_plate_input("ZZZ999"))
        assert result.total == 0

    def test_unsupported_doc_type(self):
        from openquery.sources.co.vehiculos import VehiculosSource

        src = VehiculosSource()
        with pytest.raises(SourceError, match="Unsupported"):
            src.query(QueryInput(
                document_type=DocumentType.CEDULA,
                document_number="123",
            ))

    def test_empty_brand_raises(self):
        from openquery.sources.co.vehiculos import VehiculosSource

        src = VehiculosSource()
        with pytest.raises(SourceError, match="marca"):
            src.query(_custom_input(marca=""))

    @patch("httpx.Client")
    def test_http_error(self, mock_client_cls):
        from openquery.sources.co.vehiculos import VehiculosSource

        mock_client_cls.return_value = _mock_client(
            _mock_httpx_response(None, status_code=500)
        )
        src = VehiculosSource()
        with pytest.raises(SourceError, match="HTTP 500"):
            src.query(_plate_input("ABC123"))

    @patch("httpx.Client")
    def test_unexpected_response_format(self, mock_client_cls):
        from openquery.sources.co.vehiculos import VehiculosSource

        resp = MagicMock()
        resp.json.return_value = {"error": "unexpected"}
        resp.raise_for_status.return_value = None
        mock_client_cls.return_value = _mock_client(resp)

        src = VehiculosSource()
        with pytest.raises(SourceError, match="Unexpected response"):
            src.query(_plate_input("ABC123"))

    def test_meta(self):
        from openquery.sources.co.vehiculos import VehiculosSource

        meta = VehiculosSource().meta()
        assert meta.name == "co.vehiculos"
        assert meta.country == "CO"
        assert DocumentType.PLATE in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False


# ===========================================================================
# co.peajes
# ===========================================================================

class TestPeajesSource:
    @patch("openquery.sources.co.peajes.httpx.Client")
    def test_query_by_name(self, mock_client_cls):
        from openquery.sources.co.peajes import PeajesSource

        data = [
            {"peaje": "ALVARADO", "categoria": "I", "valor": "15000"},
            {"peaje": "ALVARADO", "categoria": "II", "valor": "20000"},
        ]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = PeajesSource()
        result = src.query(_custom_input(peaje="alvarado"))
        assert result.peaje == "ALVARADO"
        assert result.total == 2
        assert result.categoria == "I"
        assert result.valor == 15000

    @patch("openquery.sources.co.peajes.httpx.Client")
    def test_query_all(self, mock_client_cls):
        from openquery.sources.co.peajes import PeajesSource

        data = [{"peaje": "TOLL_A"}, {"peaje": "TOLL_B"}]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = PeajesSource()
        result = src.query(_custom_input())
        assert result.total == 2
        assert result.peaje == ""  # No filter

    @patch("openquery.sources.co.peajes.httpx.Client")
    def test_empty_results(self, mock_client_cls):
        from openquery.sources.co.peajes import PeajesSource

        mock_client_cls.return_value = _mock_client(_mock_httpx_response([]))

        src = PeajesSource()
        result = src.query(_custom_input(peaje="NONEXISTENT"))
        assert result.total == 0

    def test_unsupported_input(self):
        from openquery.sources.co.peajes import PeajesSource

        src = PeajesSource()
        with pytest.raises(SourceError, match="Unsupported"):
            src.query(_plate_input("ABC123"))

    def test_meta(self):
        from openquery.sources.co.peajes import PeajesSource

        meta = PeajesSource().meta()
        assert meta.name == "co.peajes"
        assert meta.requires_browser is False


# ===========================================================================
# co.combustible
# ===========================================================================

class TestCombustibleSource:
    @patch("openquery.sources.co.combustible.httpx.Client")
    def test_query_by_municipio(self, mock_client_cls):
        from openquery.sources.co.combustible import CombustibleSource

        data = [
            {
                "departamento": "BOGOTA D.C.",
                "municipio": "BOGOTA  D.C.",
                "nombre_comercial": "Estacion Centro",
                "bandera": "TERPEL",
                "direccion": "Calle 1 #2-3",
                "producto": "GASOLINA",
                "precio": "9500",
            },
        ]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = CombustibleSource()
        result = src.query(_custom_input(municipio="BOGOTA"))
        assert result.total_estaciones == 1
        assert result.estaciones[0]["bandera"] == "TERPEL"
        assert result.estaciones[0]["precio"] == "9500"

    @patch("openquery.sources.co.combustible.httpx.Client")
    def test_query_by_departamento(self, mock_client_cls):
        from openquery.sources.co.combustible import CombustibleSource

        data = [{"departamento": "ANTIOQUIA", "municipio": "MEDELLIN"}]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = CombustibleSource()
        result = src.query(_custom_input(departamento="ANTIOQUIA"))
        assert result.total_estaciones == 1

    def test_no_filter_raises(self):
        from openquery.sources.co.combustible import CombustibleSource

        src = CombustibleSource()
        with pytest.raises(SourceError, match="Must provide"):
            src.query(_custom_input())

    @patch("openquery.sources.co.combustible.httpx.Client")
    def test_http_error(self, mock_client_cls):
        from openquery.sources.co.combustible import CombustibleSource

        mock_client_cls.return_value = _mock_client(
            _mock_httpx_response(None, status_code=503)
        )
        src = CombustibleSource()
        with pytest.raises(SourceError, match="HTTP 503"):
            src.query(_custom_input(municipio="X"))

    def test_meta(self):
        from openquery.sources.co.combustible import CombustibleSource

        meta = CombustibleSource().meta()
        assert meta.name == "co.combustible"
        assert meta.requires_browser is False


# ===========================================================================
# co.estaciones_ev
# ===========================================================================

class TestEstacionesEVSource:
    @patch("openquery.sources.co.estaciones_ev.httpx.Client")
    def test_query_with_city(self, mock_client_cls):
        from openquery.sources.co.estaciones_ev import EstacionesEVSource

        data = [
            {
                "tipo_de_estacion": "Estación de carga eléctrica EPM",
                "estaci_n": "Éxito Poblado",
                "ciudad": "Medellín",
                "tipo": "Semi Rápida",
                "horario": "8:00 am a 8:00 pm",
                "direcci_n": "Calle 10 # 43",
                "est_ndar_cargador": "Mennekes",
                "latitud": "6,21194987",
                "longitud": "-75,57404774",
            },
        ]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = EstacionesEVSource()
        result = src.query(_custom_input(ciudad="Medellin"))
        assert result.total == 1
        assert result.estaciones[0]["nombre"] == "Éxito Poblado"
        assert result.estaciones[0]["conector"] == "Mennekes"
        # Coordinates should have dots, not commas
        assert result.estaciones[0]["latitud"] == "6.21194987"
        assert result.estaciones[0]["longitud"] == "-75.57404774"

    @patch("openquery.sources.co.estaciones_ev.httpx.Client")
    def test_query_all_stations(self, mock_client_cls):
        from openquery.sources.co.estaciones_ev import EstacionesEVSource

        data = [
            {"estaci_n": "A", "latitud": "1,0", "longitud": "2,0"},
            {"estaci_n": "B", "latitud": "3,0", "longitud": "4,0"},
        ]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = EstacionesEVSource()
        result = src.query(_custom_input())
        assert result.total == 2
        assert result.ciudad == "ALL"

    def test_unsupported_input(self):
        from openquery.sources.co.estaciones_ev import EstacionesEVSource

        src = EstacionesEVSource()
        with pytest.raises(SourceError, match="Unsupported"):
            src.query(_plate_input("ABC123"))

    def test_meta(self):
        from openquery.sources.co.estaciones_ev import EstacionesEVSource

        meta = EstacionesEVSource().meta()
        assert meta.name == "co.estaciones_ev"
        assert meta.requires_browser is False


class TestFixCoord:
    def test_comma_to_dot(self):
        from openquery.sources.co.estaciones_ev import _fix_coord
        assert _fix_coord("6,21194987") == "6.21194987"
        assert _fix_coord("-75,574") == "-75.574"

    def test_already_dot(self):
        from openquery.sources.co.estaciones_ev import _fix_coord
        assert _fix_coord("6.211") == "6.211"

    def test_non_string(self):
        from openquery.sources.co.estaciones_ev import _fix_coord
        assert _fix_coord(123) == "123"  # type: ignore[arg-type]


# ===========================================================================
# co.siniestralidad
# ===========================================================================

class TestSiniestralidadSource:
    @patch("openquery.sources.co.siniestralidad.httpx.Client")
    def test_query_by_departamento(self, mock_client_cls):
        from openquery.sources.co.siniestralidad import SiniestralidadSource

        data = [
            {"tramo": "Ruta 40", "fallecidos": "5",
             "latitud": "4.0", "longitud": "-74.0", "pr": "10"},
            {"tramo": "Ruta 50", "fallecidos": "3",
             "latitud": "4.1", "longitud": "-74.1", "pr": "20"},
        ]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = SiniestralidadSource()
        result = src.query(_custom_input(departamento="CUNDINAMARCA"))
        assert result.total_sectores == 2
        assert result.total_fallecidos == 8
        assert result.departamento == "CUNDINAMARCA"

    @patch("openquery.sources.co.siniestralidad.httpx.Client")
    def test_query_by_municipio(self, mock_client_cls):
        from openquery.sources.co.siniestralidad import SiniestralidadSource

        data = [{"tramo": "AV 68", "fallecidos": "10"}]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = SiniestralidadSource()
        result = src.query(_custom_input(municipio="BOGOTA"))
        assert result.total_sectores == 1
        assert result.total_fallecidos == 10

    def test_no_filter_raises(self):
        from openquery.sources.co.siniestralidad import SiniestralidadSource

        src = SiniestralidadSource()
        with pytest.raises(SourceError, match="Must provide"):
            src.query(_custom_input())

    @patch("openquery.sources.co.siniestralidad.httpx.Client")
    def test_empty_results(self, mock_client_cls):
        from openquery.sources.co.siniestralidad import SiniestralidadSource

        mock_client_cls.return_value = _mock_client(_mock_httpx_response([]))

        src = SiniestralidadSource()
        result = src.query(_custom_input(departamento="NOWHERE"))
        assert result.total_sectores == 0
        assert result.total_fallecidos == 0

    @patch("openquery.sources.co.siniestralidad.httpx.Client")
    def test_missing_fallecidos_field(self, mock_client_cls):
        from openquery.sources.co.siniestralidad import SiniestralidadSource

        data = [{"tramo": "Road X"}]
        mock_client_cls.return_value = _mock_client(_mock_httpx_response(data))

        src = SiniestralidadSource()
        result = src.query(_custom_input(departamento="TEST"))
        assert result.total_fallecidos == 0

    def test_meta(self):
        from openquery.sources.co.siniestralidad import SiniestralidadSource

        meta = SiniestralidadSource().meta()
        assert meta.name == "co.siniestralidad"
        assert meta.requires_browser is False
