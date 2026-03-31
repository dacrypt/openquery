"""Unit tests for new sources (Policia, ADRES) and RUNT improvements."""

from __future__ import annotations

from openquery.models.co.adres import AdresResult
from openquery.models.co.policia import PoliciaResult
from openquery.sources.co.adres import AdresSource
from openquery.sources.co.policia import PoliciaSource
from openquery.sources.co.runt import RuntSource


class TestPoliciaResult:
    def test_default_no_records(self):
        r = PoliciaResult(cedula="12345678")
        assert r.tiene_antecedentes is False

    def test_round_trip(self):
        r = PoliciaResult(
            cedula="12345678",
            tiene_antecedentes=False,
            mensaje="No tiene asuntos pendientes",
        )
        restored = PoliciaResult.model_validate_json(r.model_dump_json())
        assert restored.mensaje == "No tiene asuntos pendientes"


class TestPoliciaSourceMeta:
    def test_meta(self):
        src = PoliciaSource()
        meta = src.meta()
        assert meta.name == "co.policia"
        assert meta.country == "CO"


class TestAdresResult:
    def test_default_values(self):
        r = AdresResult(cedula="12345678")
        assert r.eps == ""
        assert r.estado_afiliacion == ""

    def test_round_trip(self):
        r = AdresResult(
            cedula="12345678",
            eps="SURA",
            estado_afiliacion="ACTIVO",
            regimen="CONTRIBUTIVO",
        )
        restored = AdresResult.model_validate_json(r.model_dump_json())
        assert restored.eps == "SURA"
        assert restored.regimen == "CONTRIBUTIVO"


class TestAdresSourceMeta:
    def test_meta(self):
        src = AdresSource()
        meta = src.meta()
        assert meta.name == "co.adres"
        assert meta.country == "CO"


class TestRuntCedulaSupport:
    def test_meta_includes_cedula(self):
        src = RuntSource()
        meta = src.meta()
        assert "cedula" in meta.supported_inputs

    def test_soat_fields_in_model(self):
        """RuntResult should have SOAT/RTM fields."""
        from openquery.models.co.runt import RuntResult
        r = RuntResult(
            soat_vigente=True,
            soat_aseguradora="SURA",
            soat_vencimiento="2027-01-15",
            tecnomecanica_vigente=True,
            tecnomecanica_vencimiento="2027-06-30",
        )
        assert r.soat_vigente is True
        assert r.soat_aseguradora == "SURA"
        assert r.tecnomecanica_vencimiento == "2027-06-30"


class TestSourceRegistry:
    def test_all_sources_registered(self):
        from openquery.sources import list_sources
        sources = list_sources()
        names = [s.meta().name for s in sources]
        assert "co.simit" in names
        assert "co.runt" in names
        assert "co.procuraduria" in names
        assert "co.policia" in names
        assert "co.adres" in names
        assert "co.peajes" in names
        assert "co.combustible" in names
        assert "co.estaciones_ev" in names
        assert "co.siniestralidad" in names
        assert "co.vehiculos" in names
        assert "co.pico_y_placa" in names
        assert "co.fasecolda" in names
        assert "co.recalls" in names
        assert len(names) == 13
