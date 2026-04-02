"""End-to-end tests for vehicle & transit sources (browser-based).

Public test data:
- Cedula: 79940745 (Iván Duque, ex-president — public SIGEP record)
- Plate: BXM627 (generic Colombian format — may or may not return data)
- VIN: 1HGCM82633A004352 (Honda Accord — NHTSA example)

Run: uv run pytest tests/e2e/test_vehicles_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import CaptchaError, SourceError
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput

CEDULA_PUBLIC = "79940745"
PLATE_TEST = "BXM627"
VIN_TEST = "1HGCM82633A004352"


def _get_source(name: str):
    try:
        return get_source(name, timeout=45.0, headless=True)
    except TypeError:
        return get_source(name, timeout=45.0)


def _safe_query(source_name: str, doc_type: DocumentType, doc_number: str, **extra):
    src = _get_source(source_name)
    try:
        return src.query(QueryInput(
            document_type=doc_type,
            document_number=doc_number,
            extra=extra,
        ))
    except CaptchaError as e:
        pytest.skip(f"CAPTCHA failed for {source_name}: {e}")
    except SourceError as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "no hay información", "no se encontr",
                                   "ssl", "certificate", "http 404", "http 403",
                                   "could not", "captcha", "no corresponden")):
            pytest.skip(f"Transient/no-data for {source_name}: {e}")
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "net::err", "ssl", "nodename")):
            pytest.skip(f"Network/timeout for {source_name}: {e}")
        raise


# ===========================================================================
# SIMIT — Traffic fines
# ===========================================================================
@pytest.mark.integration
class TestSimitByTypeE2E:
    def test_by_cedula(self):
        result = _safe_query("co.simit", DocumentType.CEDULA, CEDULA_PUBLIC)
        assert result.comparendos >= 0
        print(f"\nSIMIT (cédula): comparendos={result.comparendos}, "
              f"deuda=${result.total_deuda:,.0f}")

    def test_by_plate(self):
        result = _safe_query("co.simit", DocumentType.PLATE, PLATE_TEST)
        assert result.comparendos >= 0
        print(f"\nSIMIT (placa): comparendos={result.comparendos}")


# ===========================================================================
# RUNT — Vehicle registry
# ===========================================================================
@pytest.mark.integration
class TestRuntByTypeE2E:
    def test_by_plate(self):
        result = _safe_query("co.runt", DocumentType.PLATE, PLATE_TEST)
        print(f"\nRUNT (placa): {result.marca} {result.linea} {result.modelo_ano}")


@pytest.mark.integration
class TestRuntConductorE2E:
    def test_conductor(self):
        result = _safe_query("co.runt_conductor", DocumentType.CEDULA, CEDULA_PUBLIC)
        print(f"\nRUNT Conductor: {result}")


@pytest.mark.integration
class TestRuntSoatE2E:
    def test_soat(self):
        result = _safe_query("co.runt_soat", DocumentType.PLATE, PLATE_TEST)
        print(f"\nRUNT SOAT: {result}")


@pytest.mark.integration
class TestRuntRtmE2E:
    def test_rtm(self):
        result = _safe_query("co.runt_rtm", DocumentType.PLATE, PLATE_TEST)
        print(f"\nRUNT RTM: {result}")


# ===========================================================================
# Comparendos & enforcement
# ===========================================================================
@pytest.mark.integration
class TestComparendosTransitoE2E:
    def test_by_cedula(self):
        result = _safe_query("co.comparendos_transito", DocumentType.CEDULA, CEDULA_PUBLIC)
        print(f"\nComparendos (cédula): {result}")

    def test_by_plate(self):
        result = _safe_query("co.comparendos_transito", DocumentType.PLATE, PLATE_TEST)
        print(f"\nComparendos (placa): {result}")


@pytest.mark.integration
class TestRetencionVehiculosE2E:
    def test_retencion(self):
        result = _safe_query("co.retencion_vehiculos", DocumentType.PLATE, PLATE_TEST)
        print(f"\nRetención Vehículos: {result}")


# ===========================================================================
# Vehicle reference data (browser)
# ===========================================================================
@pytest.mark.integration
class TestFasecoldaE2E:
    def test_tesla(self):
        result = _safe_query(
            "co.fasecolda", DocumentType.CUSTOM, "tesla",
            marca="TESLA", modelo_anio="2025",
        )
        print(f"\nFasecolda Tesla 2025: {result}")


@pytest.mark.integration
class TestRecallsE2E:
    def test_tesla_recalls(self):
        result = _safe_query(
            "co.recalls", DocumentType.CUSTOM, "tesla",
            marca="TESLA",
        )
        print(f"\nRecalls (SIC) Tesla: {result}")
