"""Tests for new sources — DO (JCE, Placas), PY (TSJE, ANTSV), UY (CorteElectoral, PJ).

Tests meta(), input validation, model roundtrips, and registry integration.
"""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# DOMINICAN REPUBLIC — do.jce
# ===========================================================================

class TestDoJceResult:
    def test_default_values(self):
        from openquery.models.do.jce import DoJceResult
        r = DoJceResult(cedula="00100000001")
        assert r.cedula == "00100000001"
        assert r.nombre == ""
        assert r.estado == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.do.jce import DoJceResult
        r = DoJceResult(cedula="00100000001", nombre="JUAN PEREZ", estado="ACTIVO")
        r2 = DoJceResult.model_validate_json(r.model_dump_json())
        assert r2.cedula == "00100000001"
        assert r2.nombre == "JUAN PEREZ"
        assert r2.estado == "ACTIVO"

    def test_audit_excluded_from_dump(self):
        from openquery.models.do.jce import DoJceResult
        r = DoJceResult(cedula="00100000001")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestDoJceSourceMeta:
    def test_meta(self):
        from openquery.sources.do.jce import DoJceSource
        meta = DoJceSource().meta()
        assert meta.name == "do.jce"
        assert meta.country == "DO"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_cedula(self):
        from openquery.sources.do.jce import DoJceSource
        src = DoJceSource()
        with pytest.raises(SourceError, match="Cédula is required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="", extra={}))


# ===========================================================================
# DOMINICAN REPUBLIC — do.placas
# ===========================================================================

class TestDoPlacasResult:
    def test_default_values(self):
        from openquery.models.do.placas import DoPlacasResult
        r = DoPlacasResult(placa="A123456")
        assert r.placa == "A123456"
        assert r.owner == ""
        assert r.plate_status == ""
        assert r.vehicle_description == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.do.placas import DoPlacasResult
        r = DoPlacasResult(
            placa="A123456",
            owner="MARIA GOMEZ",
            plate_status="ACTIVO",
            vehicle_description="TOYOTA COROLLA 2020",
        )
        r2 = DoPlacasResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "A123456"
        assert r2.owner == "MARIA GOMEZ"
        assert r2.plate_status == "ACTIVO"

    def test_audit_excluded_from_dump(self):
        from openquery.models.do.placas import DoPlacasResult
        r = DoPlacasResult(placa="A123456")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestDoPlacasSourceMeta:
    def test_meta(self):
        from openquery.sources.do.placas import DoPlacasSource
        meta = DoPlacasSource().meta()
        assert meta.name == "do.placas"
        assert meta.country == "DO"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_plate(self):
        from openquery.sources.do.placas import DoPlacasSource
        src = DoPlacasSource()
        with pytest.raises(SourceError, match="Plate number is required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="", extra={}))


# ===========================================================================
# PARAGUAY — py.tsje
# ===========================================================================

class TestPyTsjeResult:
    def test_default_values(self):
        from openquery.models.py.tsje import PyTsjeResult
        r = PyTsjeResult(ci="1234567")
        assert r.ci == "1234567"
        assert r.nombre == ""
        assert r.lugar_votacion == ""
        assert r.mesa == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.py.tsje import PyTsjeResult
        r = PyTsjeResult(
            ci="1234567",
            nombre="CARLOS LOPEZ",
            lugar_votacion="ESCUELA NACIONAL",
            mesa="001",
        )
        r2 = PyTsjeResult.model_validate_json(r.model_dump_json())
        assert r2.ci == "1234567"
        assert r2.nombre == "CARLOS LOPEZ"
        assert r2.mesa == "001"

    def test_audit_excluded_from_dump(self):
        from openquery.models.py.tsje import PyTsjeResult
        r = PyTsjeResult(ci="1234567")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestPyTsjeSourceMeta:
    def test_meta(self):
        from openquery.sources.py.tsje import PyTsjeSource
        meta = PyTsjeSource().meta()
        assert meta.name == "py.tsje"
        assert meta.country == "PY"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_ci(self):
        from openquery.sources.py.tsje import PyTsjeSource
        src = PyTsjeSource()
        with pytest.raises(SourceError, match="CI"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="", extra={}))


# ===========================================================================
# PARAGUAY — py.antsv
# ===========================================================================

class TestPyAntsvResult:
    def test_default_values(self):
        from openquery.models.py.antsv import PyAntsvResult
        r = PyAntsvResult(brand="TOYOTA", model="COROLLA", year="2020")
        assert r.brand == "TOYOTA"
        assert r.model == "COROLLA"
        assert r.year == "2020"
        assert r.taxable_value == ""
        assert r.tax_amount == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.py.antsv import PyAntsvResult
        r = PyAntsvResult(
            brand="TOYOTA",
            model="COROLLA",
            year="2020",
            taxable_value="50000000",
            tax_amount="500000",
        )
        r2 = PyAntsvResult.model_validate_json(r.model_dump_json())
        assert r2.taxable_value == "50000000"
        assert r2.tax_amount == "500000"

    def test_audit_excluded_from_dump(self):
        from openquery.models.py.antsv import PyAntsvResult
        r = PyAntsvResult()
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestPyAntsvSourceMeta:
    def test_meta(self):
        from openquery.sources.py.antsv import PyAntsvSource
        meta = PyAntsvSource().meta()
        assert meta.name == "py.antsv"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_at_least_one_field(self):
        from openquery.sources.py.antsv import PyAntsvSource
        src = PyAntsvSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))


# ===========================================================================
# URUGUAY — uy.corteelectoral
# ===========================================================================

class TestUyCorteElectoralResult:
    def test_default_values(self):
        from openquery.models.uy.corteelectoral import UyCorteElectoralResult
        r = UyCorteElectoralResult(credencial="ABC123456")
        assert r.credencial == "ABC123456"
        assert r.nombre == ""
        assert r.habilitado == ""
        assert r.lugar_votacion == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.uy.corteelectoral import UyCorteElectoralResult
        r = UyCorteElectoralResult(
            credencial="ABC123456",
            nombre="ANA MARTINEZ",
            habilitado="SI",
            lugar_votacion="LICEO 5",
        )
        r2 = UyCorteElectoralResult.model_validate_json(r.model_dump_json())
        assert r2.credencial == "ABC123456"
        assert r2.habilitado == "SI"
        assert r2.lugar_votacion == "LICEO 5"

    def test_audit_excluded_from_dump(self):
        from openquery.models.uy.corteelectoral import UyCorteElectoralResult
        r = UyCorteElectoralResult(credencial="ABC123456")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestUyCorteElectoralSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.corteelectoral import UyCorteElectoralSource
        meta = UyCorteElectoralSource().meta()
        assert meta.name == "uy.corteelectoral"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_credencial(self):
        from openquery.sources.uy.corteelectoral import UyCorteElectoralSource
        src = UyCorteElectoralSource()
        with pytest.raises(SourceError, match="Credencial"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))


# ===========================================================================
# URUGUAY — uy.pj
# ===========================================================================

class TestUyPjResult:
    def test_default_values(self):
        from openquery.models.uy.pj import UyPjResult
        r = UyPjResult(sui="2-23456/2024")
        assert r.sui == "2-23456/2024"
        assert r.case_status == ""
        assert r.last_action == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.uy.pj import UyPjResult
        r = UyPjResult(
            sui="2-23456/2024",
            case_status="EN TRAMITE",
            last_action="SENTENCIA DEFINITIVA",
        )
        r2 = UyPjResult.model_validate_json(r.model_dump_json())
        assert r2.sui == "2-23456/2024"
        assert r2.case_status == "EN TRAMITE"
        assert r2.last_action == "SENTENCIA DEFINITIVA"

    def test_audit_excluded_from_dump(self):
        from openquery.models.uy.pj import UyPjResult
        r = UyPjResult(sui="2-23456/2024")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestUyPjSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.pj import UyPjSource
        meta = UyPjSource().meta()
        assert meta.name == "uy.pj"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_sui(self):
        from openquery.sources.uy.pj import UyPjSource
        src = UyPjSource()
        with pytest.raises(SourceError, match="SUI"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))


# ===========================================================================
# Registry integration
# ===========================================================================

class TestNewSourcesRegistry:
    def test_all_six_registered(self):
        from openquery.sources import list_sources
        names = [s.meta().name for s in list_sources()]
        assert "do.jce" in names
        assert "do.placas" in names
        assert "py.tsje" in names
        assert "py.antsv" in names
        assert "uy.corteelectoral" in names
        assert "uy.pj" in names
