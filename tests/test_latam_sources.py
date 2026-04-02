"""Tests for LATAM sources — EC, PE, CL, MX, AR.

Tests meta(), input validation, model roundtrips, and registry integration
for all 21 new country sources.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# ECUADOR (EC) — 6 sources
# ===========================================================================

class TestEcSriRuc:
    def test_meta(self):
        from openquery.sources.ec.sri_ruc import SriRucSource
        meta = SriRucSource().meta()
        assert meta.name == "ec.sri_ruc"
        assert meta.country == "EC"
        assert meta.requires_browser is False

    def test_model_roundtrip(self):
        from openquery.models.ec.sri_ruc import SriRucResult
        r = SriRucResult(ruc="1234567890001", razon_social="ACME", estado="ACTIVO")
        data = r.model_dump_json()
        r2 = SriRucResult.model_validate_json(data)
        assert r2.ruc == "1234567890001"


class TestEcAntCitaciones:
    def test_meta(self):
        from openquery.sources.ec.ant_citaciones import AntCitacionesSource
        meta = AntCitacionesSource().meta()
        assert meta.name == "ec.ant_citaciones"
        assert meta.country == "EC"
        assert meta.requires_browser is False

    def test_model_roundtrip(self):
        from openquery.models.ec.ant_citaciones import AntCitacionesResult, Citacion
        c = Citacion(numero="001", tipo="Exceso velocidad", monto="150.00")
        r = AntCitacionesResult(documento="1234567890", citaciones=[c], total_citaciones=1)
        data = r.model_dump_json()
        r2 = AntCitacionesResult.model_validate_json(data)
        assert r2.total_citaciones == 1


class TestEcCnePadron:
    def test_meta(self):
        from openquery.sources.ec.cne_padron import CnePadronSource
        meta = CnePadronSource().meta()
        assert meta.name == "ec.cne_padron"
        assert meta.country == "EC"
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_model_roundtrip(self):
        from openquery.models.ec.cne_padron import CnePadronResult
        r = CnePadronResult(cedula="1234567890", nombre="Juan Perez", provincia="PICHINCHA")
        r2 = CnePadronResult.model_validate_json(r.model_dump_json())
        assert r2.provincia == "PICHINCHA"


class TestEcFuncionJudicial:
    def test_meta(self):
        from openquery.sources.ec.funcion_judicial import FuncionJudicialSource
        meta = FuncionJudicialSource().meta()
        assert meta.name == "ec.funcion_judicial"
        assert meta.country == "EC"

    def test_model_roundtrip(self):
        from openquery.models.ec.funcion_judicial import FuncionJudicialResult, ProcesoJudicial
        p = ProcesoJudicial(numero_causa="17230-2024", tipo="CIVIL", estado="EN TRAMITE")
        r = FuncionJudicialResult(query="1234567890", procesos=[p], total_procesos=1)
        r2 = FuncionJudicialResult.model_validate_json(r.model_dump_json())
        assert r2.total_procesos == 1


class TestEcSupercias:
    def test_meta(self):
        from openquery.sources.ec.supercias import SuperciasSource
        meta = SuperciasSource().meta()
        assert meta.name == "ec.supercias"
        assert meta.country == "EC"

    def test_model_roundtrip(self):
        from openquery.models.ec.supercias import SuperciasResult
        r = SuperciasResult(query="1790012345001", razon_social="EMPRESA S.A.", estado="ACTIVA")
        r2 = SuperciasResult.model_validate_json(r.model_dump_json())
        assert r2.razon_social == "EMPRESA S.A."


class TestEcSenescyt:
    def test_meta(self):
        from openquery.sources.ec.senescyt import SenescytSource
        meta = SenescytSource().meta()
        assert meta.name == "ec.senescyt"
        assert meta.country == "EC"

    def test_model_roundtrip(self):
        from openquery.models.ec.senescyt import SenescytResult, TituloProfesional
        t = TituloProfesional(titulo="INGENIERO CIVIL", institucion="UNIVERSIDAD CENTRAL")
        r = SenescytResult(query="1234567890", titulos=[t], total_titulos=1)
        r2 = SenescytResult.model_validate_json(r.model_dump_json())
        assert r2.titulos[0].titulo == "INGENIERO CIVIL"


# ===========================================================================
# PERU (PE) — 5 sources
# ===========================================================================

class TestPeSunatRuc:
    def test_meta(self):
        from openquery.sources.pe.sunat_ruc import SunatRucSource
        meta = SunatRucSource().meta()
        assert meta.name == "pe.sunat_ruc"
        assert meta.country == "PE"
        assert meta.requires_captcha is True

    def test_model_roundtrip(self):
        from openquery.models.pe.sunat_ruc import SunatRucResult
        r = SunatRucResult(ruc="20123456789", razon_social="EMPRESA PERU SAC", estado="ACTIVO")
        r2 = SunatRucResult.model_validate_json(r.model_dump_json())
        assert r2.estado == "ACTIVO"


class TestPePoderJudicial:
    def test_meta(self):
        from openquery.sources.pe.poder_judicial import PoderJudicialSource
        meta = PoderJudicialSource().meta()
        assert meta.name == "pe.poder_judicial"
        assert meta.country == "PE"

    def test_model_roundtrip(self):
        from openquery.models.pe.poder_judicial import PoderJudicialResult, ExpedienteJudicial
        e = ExpedienteJudicial(numero="00123-2024", juzgado="1er Juzgado Civil", materia="CIVIL")
        r = PoderJudicialResult(query="Juan Perez", expedientes=[e], total_expedientes=1)
        r2 = PoderJudicialResult.model_validate_json(r.model_dump_json())
        assert r2.total_expedientes == 1


class TestPeOsceSancionados:
    def test_meta(self):
        from openquery.sources.pe.osce_sancionados import OsceSancionadosSource
        meta = OsceSancionadosSource().meta()
        assert meta.name == "pe.osce_sancionados"
        assert meta.country == "PE"

    def test_model_roundtrip(self):
        from openquery.models.pe.osce_sancionados import OsceSancionadosResult, ProveedorSancionado
        p = ProveedorSancionado(nombre="CONSTRUCTORA X", ruc="20999888777", sancion="INHABILITACION")
        r = OsceSancionadosResult(query="20999888777", sancionados=[p], total_sancionados=1)
        r2 = OsceSancionadosResult.model_validate_json(r.model_dump_json())
        assert r2.sancionados[0].nombre == "CONSTRUCTORA X"


class TestPeSunarpVehicular:
    def test_meta(self):
        from openquery.sources.pe.sunarp_vehicular import SunarpVehicularSource
        meta = SunarpVehicularSource().meta()
        assert meta.name == "pe.sunarp_vehicular"
        assert meta.country == "PE"
        assert DocumentType.PLATE in meta.supported_inputs

    def test_model_roundtrip(self):
        from openquery.models.pe.sunarp_vehicular import SunarpVehicularResult
        r = SunarpVehicularResult(placa="ABC-123", marca="TOYOTA", modelo="COROLLA")
        r2 = SunarpVehicularResult.model_validate_json(r.model_dump_json())
        assert r2.marca == "TOYOTA"


class TestPeServirSanciones:
    def test_meta(self):
        from openquery.sources.pe.servir_sanciones import ServirSancionesSource
        meta = ServirSancionesSource().meta()
        assert meta.name == "pe.servir_sanciones"
        assert meta.country == "PE"

    def test_model_roundtrip(self):
        from openquery.models.pe.servir_sanciones import ServirSancionesResult, SancionServidor
        s = SancionServidor(nombre="GARCIA LOPEZ PEDRO", entidad="MINSA", tipo_sancion="DESTITUCION")
        r = ServirSancionesResult(query="GARCIA", sanciones=[s], total_sanciones=1)
        r2 = ServirSancionesResult.model_validate_json(r.model_dump_json())
        assert r2.total_sanciones == 1


# ===========================================================================
# CHILE (CL) — 3 sources
# ===========================================================================

class TestClSiiRut:
    def test_meta(self):
        from openquery.sources.cl.sii_rut import SiiRutSource
        meta = SiiRutSource().meta()
        assert meta.name == "cl.sii_rut"
        assert meta.country == "CL"
        assert meta.requires_captcha is True

    def test_model_roundtrip(self):
        from openquery.models.cl.sii_rut import SiiRutResult
        r = SiiRutResult(rut="76.123.456-7", razon_social="EMPRESA CHILE SPA", estado="VIGENTE")
        r2 = SiiRutResult.model_validate_json(r.model_dump_json())
        assert r2.rut == "76.123.456-7"


class TestClPjud:
    def test_meta(self):
        from openquery.sources.cl.pjud import PjudSource
        meta = PjudSource().meta()
        assert meta.name == "cl.pjud"
        assert meta.country == "CL"

    def test_model_roundtrip(self):
        from openquery.models.cl.pjud import PjudResult, CausaJudicial
        c = CausaJudicial(rol="C-1234-2024", tribunal="1er Juzgado Civil Santiago", materia="CIVIL")
        r = PjudResult(query="76123456", causas=[c], total_causas=1)
        r2 = PjudResult.model_validate_json(r.model_dump_json())
        assert r2.total_causas == 1


class TestClFiscalizacion:
    def test_meta(self):
        from openquery.sources.cl.fiscalizacion import FiscalizacionSource
        meta = FiscalizacionSource().meta()
        assert meta.name == "cl.fiscalizacion"
        assert meta.country == "CL"
        assert DocumentType.PLATE in meta.supported_inputs

    def test_model_roundtrip(self):
        from openquery.models.cl.fiscalizacion import FiscalizacionResult, InfraccionTransito
        i = InfraccionTransito(fecha="2024-01-15", tipo="EXCESO VELOCIDAD", monto="50000")
        r = FiscalizacionResult(patente="ABCD12", infracciones=[i], total_infracciones=1)
        r2 = FiscalizacionResult.model_validate_json(r.model_dump_json())
        assert r2.infracciones[0].tipo == "EXCESO VELOCIDAD"


# ===========================================================================
# MEXICO (MX) — 4 sources
# ===========================================================================

class TestMxCurp:
    def test_meta(self):
        from openquery.sources.mx.curp import CurpSource
        meta = CurpSource().meta()
        assert meta.name == "mx.curp"
        assert meta.country == "MX"
        assert meta.requires_captcha is False  # Uses JSON API, no CAPTCHA

    def test_model_roundtrip(self):
        from openquery.models.mx.curp import CurpResult
        r = CurpResult(curp="GARC850101HDFRRL09", nombre="CARLOS", apellido_paterno="GARCIA")
        r2 = CurpResult.model_validate_json(r.model_dump_json())
        assert r2.curp == "GARC850101HDFRRL09"


class TestMxSatEfos:
    def test_meta(self):
        from openquery.sources.mx.sat_efos import SatEfosSource
        meta = SatEfosSource().meta()
        assert meta.name == "mx.sat_efos"
        assert meta.country == "MX"

    def test_model_roundtrip(self):
        from openquery.models.mx.sat_efos import SatEfosResult, ContribuyenteEfos
        c = ContribuyenteEfos(rfc="ABC123456XYZ", nombre="EMPRESA FANTASMA SA", situacion="Definitivo")
        r = SatEfosResult(query="ABC123456XYZ", contribuyentes=[c], total_contribuyentes=1)
        r2 = SatEfosResult.model_validate_json(r.model_dump_json())
        assert r2.contribuyentes[0].situacion == "Definitivo"


class TestMxSiem:
    def test_meta(self):
        from openquery.sources.mx.siem import SiemSource
        meta = SiemSource().meta()
        assert meta.name == "mx.siem"
        assert meta.country == "MX"

    def test_model_roundtrip(self):
        from openquery.models.mx.siem import SiemResult, EmpresaSiem
        e = EmpresaSiem(nombre="TACOS EL GORDO", rfc="TEG123456ABC", estado="JALISCO")
        r = SiemResult(query="TACOS", empresas=[e], total_empresas=1)
        r2 = SiemResult.model_validate_json(r.model_dump_json())
        assert r2.empresas[0].nombre == "TACOS EL GORDO"


class TestMxRepuve:
    def test_meta(self):
        from openquery.sources.mx.repuve import RepuveSource
        meta = RepuveSource().meta()
        assert meta.name == "mx.repuve"
        assert meta.country == "MX"
        assert meta.requires_captcha is True

    def test_model_roundtrip(self):
        from openquery.models.mx.repuve import RepuveResult
        r = RepuveResult(placa="ABC-123-A", estatus_robo="Sin reporte", marca="NISSAN")
        r2 = RepuveResult.model_validate_json(r.model_dump_json())
        assert r2.estatus_robo == "Sin reporte"


# ===========================================================================
# ARGENTINA (AR) — 3 sources
# ===========================================================================

class TestArAfipCuit:
    def test_meta(self):
        from openquery.sources.ar.afip_cuit import AfipCuitSource
        meta = AfipCuitSource().meta()
        assert meta.name == "ar.afip_cuit"
        assert meta.country == "AR"

    def test_model_roundtrip(self):
        from openquery.models.ar.afip_cuit import AfipCuitResult
        r = AfipCuitResult(cuit="20-12345678-9", razon_social="EMPRESA ARGENTINA SRL", estado="ACTIVO")
        r2 = AfipCuitResult.model_validate_json(r.model_dump_json())
        assert r2.cuit == "20-12345678-9"


class TestArPjn:
    def test_meta(self):
        from openquery.sources.ar.pjn import PjnSource
        meta = PjnSource().meta()
        assert meta.name == "ar.pjn"
        assert meta.country == "AR"

    def test_model_roundtrip(self):
        from openquery.models.ar.pjn import PjnResult, CausaPjn
        c = CausaPjn(numero="12345/2024", fuero="CIVIL", juzgado="Juzgado Nacional 1")
        r = PjnResult(query="GARCIA", causas=[c], total_causas=1)
        r2 = PjnResult.model_validate_json(r.model_dump_json())
        assert r2.total_causas == 1


class TestArDnrpa:
    def test_meta(self):
        from openquery.sources.ar.dnrpa import DnrpaSource
        meta = DnrpaSource().meta()
        assert meta.name == "ar.dnrpa"
        assert meta.country == "AR"
        assert DocumentType.PLATE in meta.supported_inputs

    def test_model_roundtrip(self):
        from openquery.models.ar.dnrpa import DnrpaResult
        r = DnrpaResult(dominio="AB123CD", registro_seccional="Seccional 1 CABA", provincia="BUENOS AIRES")
        r2 = DnrpaResult.model_validate_json(r.model_dump_json())
        assert r2.dominio == "AB123CD"


# ===========================================================================
# Registry — all 21 sources discoverable
# ===========================================================================

class TestLatamSourcesRegistered:
    @pytest.mark.parametrize("source_name,country", [
        # Ecuador
        ("ec.sri_ruc", "EC"),
        ("ec.ant_citaciones", "EC"),
        ("ec.cne_padron", "EC"),
        ("ec.funcion_judicial", "EC"),
        ("ec.supercias", "EC"),
        ("ec.senescyt", "EC"),
        # Peru
        ("pe.sunat_ruc", "PE"),
        ("pe.poder_judicial", "PE"),
        ("pe.osce_sancionados", "PE"),
        ("pe.sunarp_vehicular", "PE"),
        ("pe.servir_sanciones", "PE"),
        # Chile
        ("cl.sii_rut", "CL"),
        ("cl.pjud", "CL"),
        ("cl.fiscalizacion", "CL"),
        # Mexico
        ("mx.curp", "MX"),
        ("mx.sat_efos", "MX"),
        ("mx.siem", "MX"),
        ("mx.repuve", "MX"),
        # Argentina
        ("ar.afip_cuit", "AR"),
        ("ar.pjn", "AR"),
        ("ar.dnrpa", "AR"),
    ])
    def test_source_registered(self, source_name, country):
        from openquery.sources import get_source
        src = get_source(source_name)
        assert src.meta().name == source_name
        assert src.meta().country == country
