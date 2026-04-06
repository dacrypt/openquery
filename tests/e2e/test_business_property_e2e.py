"""End-to-end tests for business, property & compliance sources (browser-based).

Public test data:
- Cedula: 79940745 (Iván Duque, ex-president — public SIGEP record)
- NIT: 899999068 (Ecopetrol S.A. — public company)

Run: uv run pytest tests/e2e/test_business_property_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import CaptchaError, SourceError
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput

CEDULA_PUBLIC = "79940745"
NIT_PUBLIC = "899999068"


def _get_source(source_name: str):
    """Get source with appropriate kwargs based on whether it needs a browser."""
    try:
        return get_source(source_name, timeout=45.0, headless=True)
    except TypeError:
        return get_source(source_name, timeout=45.0)


def _safe_query(
    source_name: str,
    doc_type: DocumentType = DocumentType.CEDULA,
    doc_number: str = CEDULA_PUBLIC,
    **extra,
):
    src = _get_source(source_name)
    try:
        return src.query(
            QueryInput(
                document_type=doc_type,
                document_number=doc_number,
                extra=extra,
            )
        )
    except CaptchaError as e:
        pytest.skip(f"CAPTCHA failed for {source_name}: {e}")
    except SourceError as e:
        msg = str(e).lower()
        if any(
            k in msg for k in ("timeout", "ssl", "certificate", "http 404", "http 403", "could not")
        ):
            pytest.skip(f"Transient failure for {source_name}: {e}")
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "net::err", "ssl", "nodename")):
            pytest.skip(f"Network/timeout for {source_name}: {e}")
        raise


# ===========================================================================
# Business & commerce
# ===========================================================================
@pytest.mark.integration
class TestDianRutE2E:
    def test_rut_cedula(self):
        result = _safe_query("co.dian_rut")
        print(f"\nDIAN RUT (cédula): {result}")

    def test_rut_nit(self):
        result = _safe_query("co.dian_rut", DocumentType.NIT, NIT_PUBLIC)
        print(f"\nDIAN RUT (NIT Ecopetrol): {result}")


@pytest.mark.integration
class TestRuesE2E:
    def test_rues_cedula(self):
        result = _safe_query("co.rues")
        print(f"\nRUES (cédula): {result}")

    def test_rues_nit(self):
        result = _safe_query("co.rues", DocumentType.NIT, NIT_PUBLIC)
        print(f"\nRUES (NIT Ecopetrol): {result}")


@pytest.mark.integration
class TestProveedoresFicticiosE2E:
    def test_ecopetrol(self):
        result = _safe_query("co.proveedores_ficticios", DocumentType.NIT, NIT_PUBLIC)
        print(f"\nProveedores Ficticios Ecopetrol: {result}")


# ===========================================================================
# Property & real estate
# ===========================================================================
@pytest.mark.integration
class TestSnrE2E:
    def test_snr_cedula(self):
        result = _safe_query("co.snr")
        print(f"\nSNR (cédula): {result}")


@pytest.mark.integration
class TestGarantiasMobiliariasE2E:
    def test_garantias(self):
        result = _safe_query("co.garantias_mobiliarias")
        print(f"\nGarantías Mobiliarias: {result}")


@pytest.mark.integration
class TestCambioEstratoE2E:
    def test_estrato(self):
        result = _safe_query("co.cambio_estrato")
        print(f"\nCambio Estrato: {result}")


# ===========================================================================
# Housing
# ===========================================================================
@pytest.mark.integration
class TestMiCasaYaE2E:
    def test_mi_casa_ya(self):
        result = _safe_query("co.mi_casa_ya")
        print(f"\nMi Casa Ya: {result}")
