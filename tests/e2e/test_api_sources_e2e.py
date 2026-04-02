"""End-to-end tests for API-only sources (no browser required).

These sources use direct HTTP calls — fast and reliable.
Tests hit real external APIs and require network access.

Public test data:
- Cedula: 79940745 (Iván Duque, ex-president — public SIGEP record)
- NIT: 899999068 (Ecopetrol S.A. — public company)
- VIN: 1HGCM82633A004352 (Honda Accord — NHTSA example)

Run: uv run pytest tests/e2e/test_api_sources_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput

# ---------------------------------------------------------------------------
# Public test data
# ---------------------------------------------------------------------------
CEDULA_PUBLIC = "79940745"        # Iván Duque — ex-president (SIGEP public)
NIT_PUBLIC = "899999068"          # Ecopetrol S.A.
VIN_NHTSA = "1HGCM82633A004352"  # Honda Accord — NHTSA example VIN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _query(source_name: str, doc_type: DocumentType, doc_number: str, **extra):
    src = get_source(source_name)
    try:
        return src.query(QueryInput(
            document_type=doc_type,
            document_number=doc_number,
            extra=extra,
        ))
    except SourceError as e:
        msg = str(e).lower()
        if "ssl" in msg or "certificate" in msg:
            pytest.skip(f"SSL/cert issue for {source_name}: {e}")
        if "nodename nor servname" in msg or "name resolution" in msg:
            pytest.skip(f"DNS resolution failed for {source_name}: {e}")
        if "http 404" in msg or "http 403" in msg or "http 302" in msg:
            pytest.skip(f"API endpoint unavailable for {source_name}: {e}")
        raise
    except Exception as e:
        msg = str(e).lower()
        if "ssl" in msg or "certificate" in msg or "nodename" in msg:
            pytest.skip(f"Network issue for {source_name}: {e}")
        raise


# ===========================================================================
# International sanctions
# ===========================================================================
@pytest.mark.integration
class TestOfacE2E:
    """OFAC SDN sanctions screening — US Treasury."""

    def test_clean_cedula(self):
        result = _query("us.ofac", DocumentType.CEDULA, CEDULA_PUBLIC)
        assert hasattr(result, "match_count")
        assert result.match_count >= 0
        print(f"\nOFAC: match_count={result.match_count}, sanctioned={result.is_sanctioned}")

    def test_known_sanctioned_name(self):
        """Search a name known to appear on the SDN list."""
        result = _query("us.ofac", DocumentType.CUSTOM, "Nicolas Maduro")
        assert result.match_count > 0
        assert result.is_sanctioned is True
        print(f"\nOFAC 'Nicolas Maduro': {result.match_count} matches")


@pytest.mark.integration
class TestOnuE2E:
    """UN Security Council sanctions list."""

    def test_clean_cedula(self):
        result = _query("intl.onu", DocumentType.CEDULA, CEDULA_PUBLIC)
        assert result.match_count >= 0
        print(f"\nONU: match_count={result.match_count}")


# ===========================================================================
# NHTSA / EPA (US vehicle data)
# ===========================================================================
@pytest.mark.integration
class TestNhtsaVinE2E:
    """NHTSA VIN decoder — vPIC API."""

    def test_decode_honda_vin(self):
        result = _query("us.nhtsa_vin", DocumentType.VIN, VIN_NHTSA)
        assert hasattr(result, "make")
        assert "honda" in result.make.lower()
        print(f"\nNHTSA VIN: {result.model_year} {result.make} {result.model}")
        print(f"  Plant: {result.plant_country}")
        print(f"  Body: {result.body_class}")


@pytest.mark.integration
class TestNhtsaRecallsE2E:
    """NHTSA vehicle recalls."""

    def test_tesla_recalls(self):
        result = _query(
            "us.nhtsa_recalls", DocumentType.CUSTOM, "tesla_model_y",
            make="TESLA", model="Model Y", year="2024",
        )
        assert hasattr(result, "recalls")
        print(f"\nNHTSA Recalls Tesla Model Y 2024: {len(result.recalls)} recalls")
        for r in result.recalls[:3]:
            print(f"  - {r.campaign_number}: {r.summary[:80]}...")


@pytest.mark.integration
class TestNhtsaComplaintsE2E:
    """NHTSA vehicle safety complaints."""

    def test_tesla_complaints(self):
        # NHTSA uses "MODEL 3" not "Model 3" — uppercase with space
        result = _query(
            "us.nhtsa_complaints", DocumentType.CUSTOM, "tesla_model_3",
            make="TESLA", model="MODEL 3", year="2023",
        )
        assert hasattr(result, "complaints")
        assert result.total_complaints > 0
        print(f"\nNHTSA Complaints Tesla MODEL 3 2023: {result.total_complaints} complaints")


@pytest.mark.integration
class TestEpaFuelEconomyE2E:
    """EPA fuel economy ratings."""

    def test_toyota_camry_fuel_economy(self):
        """Toyota Camry — widely available in EPA database."""
        result = _query(
            "us.epa_fuel_economy", DocumentType.CUSTOM, "camry",
            make="Toyota", model="Camry", year="2024",
        )
        assert hasattr(result, "vehicles")
        assert result.total > 0
        print(f"\nEPA Toyota Camry 2024: {result.total} variants")
        for v in result.vehicles[:3]:
            print(f"  - {v.year} {v.make} {v.model}: {v.city_mpg}/{v.highway_mpg} mpg")


# ===========================================================================
# Colombian compliance (API-only)
# ===========================================================================
@pytest.mark.integration
class TestPepE2E:
    """PEP — Politically Exposed Persons (SIGEP)."""

    def test_public_official(self):
        """Iván Duque should appear as a PEP."""
        result = _query("co.pep", DocumentType.CEDULA, CEDULA_PUBLIC)
        assert hasattr(result, "is_pep")
        print(f"\nPEP: is_pep={result.is_pep}, entries={len(result.entries) if hasattr(result, 'entries') else 'N/A'}")


@pytest.mark.integration
class TestSecopE2E:
    """SECOP — Public procurement contracts."""

    def test_public_company(self):
        result = _query("co.secop", DocumentType.CEDULA, CEDULA_PUBLIC)
        assert result.total_contratos >= 0
        print(f"\nSECOP: {result.total_contratos} contratos")


# ===========================================================================
# Colombian open data (Socrata / API)
# ===========================================================================
@pytest.mark.integration
class TestPicoYPlacaE2E:
    """Pico y placa driving restrictions."""

    def test_valid_plate_format(self):
        result = _query("co.pico_y_placa", DocumentType.PLATE, "BXM627")
        assert hasattr(result, "placa") or hasattr(result, "restricciones")
        print(f"\nPico y Placa BXM627: {result}")


@pytest.mark.integration
class TestVehiculosE2E:
    """National vehicle fleet data (Socrata)."""

    def test_query_by_plate(self):
        result = _query("co.vehiculos", DocumentType.PLATE, "BXM627")
        print(f"\nVehiculos BXM627: {result}")


@pytest.mark.integration
class TestPeajesE2E:
    """Toll road tariffs."""

    def test_bogota_tolls(self):
        result = _query("co.peajes", DocumentType.CUSTOM, "tolls", nombre="BOGOTA")
        assert result.total > 0
        print(f"\nPeajes: {result.total} resultados")


@pytest.mark.integration
class TestCombustibleE2E:
    """Fuel prices."""

    def test_medellin_prices(self):
        result = _query("co.combustible", DocumentType.CUSTOM, "fuel", municipio="MEDELLIN")
        print(f"\nCombustible Medellin: {result}")


@pytest.mark.integration
class TestEstacionesEvE2E:
    """EV charging stations."""

    def test_bogota_stations(self):
        result = _query("co.estaciones_ev", DocumentType.CUSTOM, "ev", ciudad="BOGOTA")
        print(f"\nEstaciones EV Bogota: {result}")


@pytest.mark.integration
class TestSiniestraliadE2E:
    """Road crash hotspots."""

    def test_antioquia(self):
        result = _query(
            "co.siniestralidad", DocumentType.CUSTOM, "safety",
            departamento="ANTIOQUIA",
        )
        print(f"\nSiniestralidad Antioquia: {result}")


@pytest.mark.integration
class TestTarifasEnergiaE2E:
    """Electricity tariffs."""

    def test_medellin(self):
        result = _query(
            "co.tarifas_energia", DocumentType.CUSTOM, "energy",
            municipio="MEDELLIN",
        )
        print(f"\nTarifas Energia Medellin: {result}")


@pytest.mark.integration
class TestLicenciasSaludE2E:
    """Health service providers (REPS)."""

    def test_ecopetrol_nit(self):
        result = _query("co.licencias_salud", DocumentType.NIT, NIT_PUBLIC)
        print(f"\nLicencias Salud Ecopetrol: {result}")


@pytest.mark.integration
class TestRntTurismoE2E:
    """National tourism registry."""

    def test_by_nit(self):
        result = _query("co.rnt_turismo", DocumentType.NIT, NIT_PUBLIC)
        print(f"\nRNT Turismo Ecopetrol: {result}")
