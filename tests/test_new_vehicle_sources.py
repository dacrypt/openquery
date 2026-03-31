"""Unit tests for the 8 new vehicle-related sources.

Covers: pico_y_placa, peajes, combustible, estaciones_ev,
        siniestralidad, vehiculos, fasecolda, recalls.
"""

from __future__ import annotations

from openquery.models.co.combustible import CombustibleResult
from openquery.models.co.estaciones_ev import EstacionEVResult
from openquery.models.co.fasecolda import FasecoldaResult
from openquery.models.co.peajes import PeajeResult
from openquery.models.co.pico_y_placa import PicoYPlacaResult
from openquery.models.co.recalls import RecallResult
from openquery.models.co.siniestralidad import SiniestralidadResult
from openquery.models.co.vehiculos import VehiculosResult
from openquery.sources.co.combustible import CombustibleSource
from openquery.sources.co.estaciones_ev import EstacionesEVSource
from openquery.sources.co.fasecolda import FasecoldaSource
from openquery.sources.co.peajes import PeajesSource
from openquery.sources.co.pico_y_placa import PicoYPlacaSource
from openquery.sources.co.recalls import RecallsSource
from openquery.sources.co.siniestralidad import SiniestralidadSource
from openquery.sources.co.vehiculos import VehiculosSource

# ── Pico y Placa ──────────────────────────────────────────────────────


class TestPicoYPlacaResult:
    def test_default_values(self):
        r = PicoYPlacaResult()
        assert r.placa == ""
        assert r.restringido is False
        assert r.exento is False
        assert r.horario == ""

    def test_round_trip(self):
        r = PicoYPlacaResult(
            placa="ABC123",
            ultimo_digito="3",
            ciudad="bogota",
            fecha="2026-04-06",
            restringido=True,
            horario="6:00 AM - 9:00 PM",
            motivo="Dia par: placas 1-5 restringidas",
            tipo_vehiculo="particular",
        )
        restored = PicoYPlacaResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC123"
        assert restored.restringido is True
        assert restored.horario == "6:00 AM - 9:00 PM"

    def test_audit_excluded_from_dump(self):
        r = PicoYPlacaResult(placa="XYZ789", audit={"screenshot": "data"})
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestPicoYPlacaSourceMeta:
    def test_meta(self):
        src = PicoYPlacaSource()
        meta = src.meta()
        assert meta.name == "co.pico_y_placa"
        assert meta.country == "CO"
        assert "placa" in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.requires_captcha is False


class TestPicoYPlacaBogota:
    """Bogota: even calendar day restricts 1-5, odd day restricts 6-0."""

    def _make_source(self) -> PicoYPlacaSource:
        return PicoYPlacaSource()

    def _query(self, src, placa: str, fecha: str, ciudad: str = "bogota"):
        from openquery.sources.base import DocumentType, QueryInput

        inp = QueryInput(
            document_type=DocumentType.PLATE,
            document_number=placa,
            extra={"ciudad": ciudad, "fecha": fecha},
        )
        return src.query(inp)

    def test_even_day_restricts_1_to_5(self):
        src = self._make_source()
        # 2026-04-06 is Monday, day 6 is even, not a holiday
        for digit in range(1, 6):
            result = self._query(src, f"ABC00{digit}", "2026-04-06")
            assert result.restringido is True, f"digit {digit} should be restricted on even day"

    def test_even_day_allows_6_to_0(self):
        src = self._make_source()
        # 2026-04-06 day 6 is even
        for digit in [6, 7, 8, 9, 0]:
            result = self._query(src, f"ABC00{digit}", "2026-04-06")
            assert not result.restringido, f"digit {digit} not restricted"

    def test_odd_day_restricts_6_to_0(self):
        src = self._make_source()
        # 2026-04-07 is Tuesday, day 7 is odd, not a holiday
        for digit in [6, 7, 8, 9, 0]:
            result = self._query(src, f"ABC00{digit}", "2026-04-07")
            assert result.restringido is True, f"digit {digit} should be restricted on odd day"

    def test_odd_day_allows_1_to_5(self):
        src = self._make_source()
        # 2026-04-07 day 7 is odd
        for digit in range(1, 6):
            result = self._query(src, f"ABC00{digit}", "2026-04-07")
            assert result.restringido is False, f"digit {digit} should NOT be restricted on odd day"

    def test_weekend_saturday_no_restriction(self):
        src = self._make_source()
        # 2026-04-04 is Saturday
        result = self._query(src, "ABC001", "2026-04-04")
        assert result.restringido is False
        assert "Fin de semana" in result.motivo

    def test_weekend_sunday_no_restriction(self):
        src = self._make_source()
        # 2026-04-05 is Sunday
        result = self._query(src, "ABC006", "2026-04-05")
        assert result.restringido is False

    def test_holiday_no_restriction(self):
        src = self._make_source()
        # 2026-05-01 is Dia del Trabajo (Friday)
        result = self._query(src, "ABC001", "2026-05-01")
        assert result.restringido is False
        assert "festivo" in result.motivo


class TestPicoYPlacaMedellin:
    """Medellin: Mon=1,7 Tue=0,3 Wed=4,6 Thu=5,9 Fri=2,8."""

    def _query(self, placa: str, fecha: str):
        from openquery.sources.base import DocumentType, QueryInput

        src = PicoYPlacaSource()
        inp = QueryInput(
            document_type=DocumentType.PLATE,
            document_number=placa,
            extra={"ciudad": "medellin", "fecha": fecha},
        )
        return src.query(inp)

    def test_monday_restricts_1_and_7(self):
        # 2026-04-06 is Monday
        assert self._query("ABC001", "2026-04-06").restringido is True
        assert self._query("ABC007", "2026-04-06").restringido is True
        assert self._query("ABC002", "2026-04-06").restringido is False

    def test_tuesday_restricts_0_and_3(self):
        # 2026-04-07 is Tuesday
        assert self._query("ABC000", "2026-04-07").restringido is True
        assert self._query("ABC003", "2026-04-07").restringido is True
        assert self._query("ABC005", "2026-04-07").restringido is False

    def test_wednesday_restricts_4_and_6(self):
        # 2026-04-08 is Wednesday
        assert self._query("ABC004", "2026-04-08").restringido is True
        assert self._query("ABC006", "2026-04-08").restringido is True
        assert self._query("ABC001", "2026-04-08").restringido is False

    def test_thursday_restricts_5_and_9(self):
        # 2026-04-09 is Thursday
        assert self._query("ABC005", "2026-04-09").restringido is True
        assert self._query("ABC009", "2026-04-09").restringido is True
        assert self._query("ABC002", "2026-04-09").restringido is False

    def test_friday_restricts_2_and_8(self):
        # 2026-04-10 is Friday
        assert self._query("ABC002", "2026-04-10").restringido is True
        assert self._query("ABC008", "2026-04-10").restringido is True
        assert self._query("ABC003", "2026-04-10").restringido is False

    def test_weekend_no_restriction(self):
        # 2026-04-11 is Saturday
        assert self._query("ABC001", "2026-04-11").restringido is False


class TestPicoYPlacaCali:
    """Cali: Mon=1,2 Tue=3,4 Wed=5,6 Thu=7,8 Fri=9,0."""

    def _query(self, placa: str, fecha: str):
        from openquery.sources.base import DocumentType, QueryInput

        src = PicoYPlacaSource()
        inp = QueryInput(
            document_type=DocumentType.PLATE,
            document_number=placa,
            extra={"ciudad": "cali", "fecha": fecha},
        )
        return src.query(inp)

    def test_monday_restricts_1_and_2(self):
        # 2026-04-06 is Monday
        assert self._query("ABC001", "2026-04-06").restringido is True
        assert self._query("ABC002", "2026-04-06").restringido is True
        assert self._query("ABC003", "2026-04-06").restringido is False

    def test_tuesday_restricts_3_and_4(self):
        # 2026-04-07 is Tuesday
        assert self._query("ABC003", "2026-04-07").restringido is True
        assert self._query("ABC004", "2026-04-07").restringido is True
        assert self._query("ABC001", "2026-04-07").restringido is False

    def test_wednesday_restricts_5_and_6(self):
        # 2026-04-08 is Wednesday
        assert self._query("ABC005", "2026-04-08").restringido is True
        assert self._query("ABC006", "2026-04-08").restringido is True
        assert self._query("ABC007", "2026-04-08").restringido is False

    def test_thursday_restricts_7_and_8(self):
        # 2026-04-09 is Thursday
        assert self._query("ABC007", "2026-04-09").restringido is True
        assert self._query("ABC008", "2026-04-09").restringido is True
        assert self._query("ABC001", "2026-04-09").restringido is False

    def test_friday_restricts_9_and_0(self):
        # 2026-04-10 is Friday
        assert self._query("ABC009", "2026-04-10").restringido is True
        assert self._query("ABC000", "2026-04-10").restringido is True
        assert self._query("ABC001", "2026-04-10").restringido is False

    def test_weekend_no_restriction(self):
        # 2026-04-12 is Sunday
        assert self._query("ABC009", "2026-04-12").restringido is False


# ── Peajes (Socrata API) ─────────────────────────────────────────────


class TestPeajeResult:
    def test_default_values(self):
        r = PeajeResult()
        assert r.peaje == ""
        assert r.valor == 0
        assert r.resultados == []

    def test_round_trip(self):
        r = PeajeResult(peaje="CALAMAR", valor=15400, categoria="I")
        restored = PeajeResult.model_validate_json(r.model_dump_json())
        assert restored.peaje == "CALAMAR"
        assert restored.valor == 15400

    def test_audit_excluded_from_dump(self):
        r = PeajeResult(peaje="TEST", audit={"trace": True})
        assert "audit" not in r.model_dump()


class TestPeajesSourceMeta:
    def test_meta(self):
        src = PeajesSource()
        meta = src.meta()
        assert meta.name == "co.peajes"
        assert meta.country == "CO"
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.requires_captcha is False


# ── Combustible (Socrata API) ────────────────────────────────────────


class TestCombustibleResult:
    def test_default_values(self):
        r = CombustibleResult()
        assert r.departamento == ""
        assert r.municipio == ""
        assert r.estaciones == []
        assert r.total_estaciones == 0

    def test_round_trip(self):
        r = CombustibleResult(
            departamento="CUNDINAMARCA",
            municipio="BOGOTA",
            total_estaciones=3,
            estaciones=[{"nombre": "TERPEL", "precio": "9500"}],
        )
        restored = CombustibleResult.model_validate_json(r.model_dump_json())
        assert restored.departamento == "CUNDINAMARCA"
        assert restored.total_estaciones == 3
        assert len(restored.estaciones) == 1

    def test_audit_excluded_from_dump(self):
        r = CombustibleResult(audit={"log": "x"})
        assert "audit" not in r.model_dump()


class TestCombustibleSourceMeta:
    def test_meta(self):
        src = CombustibleSource()
        meta = src.meta()
        assert meta.name == "co.combustible"
        assert meta.country == "CO"
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.requires_captcha is False


# ── Estaciones EV (Socrata API) ──────────────────────────────────────


class TestEstacionEVResult:
    def test_default_values(self):
        r = EstacionEVResult()
        assert r.ciudad == ""
        assert r.estaciones == []
        assert r.total == 0

    def test_round_trip(self):
        r = EstacionEVResult(
            ciudad="MEDELLIN",
            total=2,
            estaciones=[{"nombre": "EPM Centro", "conector": "CCS2"}],
        )
        restored = EstacionEVResult.model_validate_json(r.model_dump_json())
        assert restored.ciudad == "MEDELLIN"
        assert restored.total == 2

    def test_audit_excluded_from_dump(self):
        r = EstacionEVResult(audit={"x": 1})
        assert "audit" not in r.model_dump()


class TestEstacionesEVSourceMeta:
    def test_meta(self):
        src = EstacionesEVSource()
        meta = src.meta()
        assert meta.name == "co.estaciones_ev"
        assert meta.country == "CO"
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.requires_captcha is False


# ── Siniestralidad (Socrata API) ─────────────────────────────────────


class TestSiniestralidadResult:
    def test_default_values(self):
        r = SiniestralidadResult()
        assert r.departamento == ""
        assert r.municipio == ""
        assert r.sectores == []
        assert r.total_sectores == 0
        assert r.total_fallecidos == 0

    def test_round_trip(self):
        r = SiniestralidadResult(
            departamento="ANTIOQUIA",
            municipio="MEDELLIN",
            total_sectores=5,
            total_fallecidos=12,
            sectores=[{"tramo": "Km 10", "fallecidos": 3}],
        )
        restored = SiniestralidadResult.model_validate_json(r.model_dump_json())
        assert restored.total_fallecidos == 12
        assert len(restored.sectores) == 1

    def test_audit_excluded_from_dump(self):
        r = SiniestralidadResult(audit={"pdf": b"..."})
        assert "audit" not in r.model_dump()


class TestSiniestralidadSourceMeta:
    def test_meta(self):
        src = SiniestralidadSource()
        meta = src.meta()
        assert meta.name == "co.siniestralidad"
        assert meta.country == "CO"
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.requires_captcha is False


# ── Vehiculos (Socrata API) ──────────────────────────────────────────


class TestVehiculosResult:
    def test_default_values(self):
        r = VehiculosResult()
        assert r.placa == ""
        assert r.marca == ""
        assert r.cilindraje == 0
        assert r.total == 0
        assert r.resultados == []

    def test_round_trip(self):
        r = VehiculosResult(
            placa="ABC123",
            clase="AUTOMOVIL",
            marca="CHEVROLET",
            modelo="2020",
            servicio="PARTICULAR",
            cilindraje=1500,
            total=1,
        )
        restored = VehiculosResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC123"
        assert restored.marca == "CHEVROLET"
        assert restored.cilindraje == 1500

    def test_audit_excluded_from_dump(self):
        r = VehiculosResult(audit={"trace": True})
        assert "audit" not in r.model_dump()


class TestVehiculosSourceMeta:
    def test_meta(self):
        src = VehiculosSource()
        meta = src.meta()
        assert meta.name == "co.vehiculos"
        assert meta.country == "CO"
        assert "placa" in meta.supported_inputs
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.requires_captcha is False


# ── Fasecolda ────────────────────────────────────────────────────────


class TestFasecoldaResult:
    def test_default_values(self):
        r = FasecoldaResult()
        assert r.marca == ""
        assert r.linea == ""
        assert r.modelo == 0
        assert r.valor == 0
        assert r.cilindraje == 0
        assert r.combustible == ""
        assert r.codigo_fasecolda == ""
        assert r.resultados == []

    def test_round_trip(self):
        r = FasecoldaResult(
            marca="TESLA",
            linea="MODEL Y",
            modelo=2026,
            valor=280_000_000,
            cilindraje=0,
            combustible="ELECTRICO",
            transmision="AUTOMATICA",
            puertas=5,
            pasajeros=5,
            codigo_fasecolda="99001",
        )
        restored = FasecoldaResult.model_validate_json(r.model_dump_json())
        assert restored.marca == "TESLA"
        assert restored.valor == 280_000_000
        assert restored.combustible == "ELECTRICO"

    def test_audit_excluded_from_dump(self):
        r = FasecoldaResult(marca="X", audit={"pdf": b"..."})
        assert "audit" not in r.model_dump()


class TestFasecoldaSourceMeta:
    def test_meta(self):
        src = FasecoldaSource()
        meta = src.meta()
        assert meta.name == "co.fasecolda"
        assert meta.country == "CO"
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False


# ── Recalls ──────────────────────────────────────────────────────────


class TestRecallResult:
    def test_default_values(self):
        r = RecallResult()
        assert r.marca == ""
        assert r.modelo == ""
        assert r.total_campanias == 0
        assert r.campanias == []

    def test_round_trip(self):
        r = RecallResult(
            marca="CHEVROLET",
            total_campanias=2,
            campanias=[
                {"componente": "AIRBAG", "descripcion": "Inflador defectuoso"},
                {"componente": "FRENOS", "descripcion": "Pastillas con desgaste"},
            ],
        )
        restored = RecallResult.model_validate_json(r.model_dump_json())
        assert restored.marca == "CHEVROLET"
        assert restored.total_campanias == 2
        assert len(restored.campanias) == 2

    def test_audit_excluded_from_dump(self):
        r = RecallResult(marca="X", audit={"pdf": b"..."})
        assert "audit" not in r.model_dump()


class TestRecallsSourceMeta:
    def test_meta(self):
        src = RecallsSource()
        meta = src.meta()
        assert meta.name == "co.recalls"
        assert meta.country == "CO"
        assert "custom" in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False
