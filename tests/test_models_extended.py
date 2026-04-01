"""Extended model tests — common, fasecolda, vehiculos, all models JSON roundtrip."""

from __future__ import annotations

from openquery.models.co.combustible import CombustibleResult
from openquery.models.co.estaciones_ev import EstacionEVResult
from openquery.models.co.fasecolda import FasecoldaResult
from openquery.models.co.peajes import PeajeResult
from openquery.models.co.pico_y_placa import PicoYPlacaResult
from openquery.models.co.policia import PoliciaResult
from openquery.models.co.recalls import RecallResult
from openquery.models.co.siniestralidad import SiniestralidadResult
from openquery.models.co.vehiculos import VehiculosResult
from openquery.models.common import QueryResult


class TestQueryResultCommon:
    def test_defaults(self):
        r = QueryResult()
        assert r.ok is True
        assert r.source == ""
        assert r.cached is False
        assert r.error is None
        assert r.retryable is False

    def test_error_response(self):
        r = QueryResult(ok=False, error="timeout", detail="connection lost")
        assert r.ok is False
        assert r.error == "timeout"

    def test_json_roundtrip(self):
        r = QueryResult(
            ok=True,
            source="co.test",
            data={"key": "value"},
        )
        data = r.model_dump(mode="json")
        r2 = QueryResult(**data)
        assert r2.source == "co.test"
        assert r2.data == {"key": "value"}


class TestFasecoldaResult:
    def test_defaults(self):
        r = FasecoldaResult()
        assert r.marca == ""
        assert r.valor == 0
        assert r.resultados == []

    def test_full_result(self):
        r = FasecoldaResult(
            marca="TESLA",
            linea="MODEL 3",
            modelo=2026,
            valor=180000000,
            cilindraje=0,
            combustible="ELECTRICO",
            transmision="AUTOMATICA",
            puertas=4,
            pasajeros=5,
            codigo_fasecolda="ABC123",
            resultados=[{"ref": 1}],
        )
        assert r.marca == "TESLA"
        assert r.valor == 180000000
        assert r.combustible == "ELECTRICO"

    def test_json_roundtrip(self):
        r = FasecoldaResult(marca="CHEVROLET", modelo=2024, valor=50000000)
        data = r.model_dump(mode="json")
        r2 = FasecoldaResult(**data)
        assert r2.marca == r.marca
        assert r2.valor == r.valor


class TestVehiculosResult:
    def test_defaults(self):
        r = VehiculosResult()
        assert r.placa == ""
        assert r.total == 0
        assert r.resultados == []

    def test_full_result(self):
        r = VehiculosResult(
            placa="ABC123",
            clase="AUTOMOVIL",
            marca="RENAULT",
            modelo="2020",
            servicio="PARTICULAR",
            cilindraje=1600,
            total=1,
            resultados=[{"placa": "ABC123"}],
        )
        assert r.placa == "ABC123"
        assert r.cilindraje == 1600

    def test_json_roundtrip(self):
        r = VehiculosResult(marca="HONDA", total=5)
        data = r.model_dump(mode="json")
        r2 = VehiculosResult(**data)
        assert r2.marca == r.marca


class TestRecallResult:
    def test_defaults(self):
        r = RecallResult()
        assert r.marca == ""
        assert r.total_campanias == 0
        assert r.campanias == []

    def test_with_campaigns(self):
        r = RecallResult(
            marca="TESLA",
            total_campanias=2,
            campanias=[
                {"componente": "frenos", "descripcion": "recall 1"},
                {"componente": "airbag", "descripcion": "recall 2"},
            ],
        )
        assert r.total_campanias == 2


class TestAllModelsJsonRoundtrip:
    """Verify every model can serialize and deserialize."""

    def test_combustible(self):
        r = CombustibleResult(municipio="BOGOTA", total_estaciones=5)
        assert CombustibleResult(**r.model_dump(mode="json"))

    def test_estacion_ev(self):
        r = EstacionEVResult(ciudad="MEDELLIN", total=10)
        assert EstacionEVResult(**r.model_dump(mode="json"))

    def test_peaje(self):
        r = PeajeResult(peaje="TEST", total=3)
        assert PeajeResult(**r.model_dump(mode="json"))

    def test_pico_y_placa(self):
        r = PicoYPlacaResult(placa="ABC123", restringido=True)
        assert PicoYPlacaResult(**r.model_dump(mode="json"))

    def test_siniestralidad(self):
        r = SiniestralidadResult(departamento="TEST", total_sectores=5)
        assert SiniestralidadResult(**r.model_dump(mode="json"))

    def test_policia(self):
        r = PoliciaResult(cedula="123", tiene_antecedentes=False)
        assert PoliciaResult(**r.model_dump(mode="json"))
