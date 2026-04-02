"""End-to-end tests for social security & health sources (browser-based).

Public test data:
- Cedula: 79940745 (Iván Duque, ex-president — public SIGEP record)

Run: uv run pytest tests/e2e/test_social_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import CaptchaError, SourceError
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput

CEDULA_PUBLIC = "79940745"


def _get_source(name: str):
    try:
        return get_source(name, timeout=45.0, headless=True)
    except TypeError:
        return get_source(name, timeout=45.0)


def _safe_query(source_name: str, doc_type: DocumentType = DocumentType.CEDULA,
                doc_number: str = CEDULA_PUBLIC, **extra):
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
        if any(k in msg for k in ("timeout", "ssl", "certificate", "http 404", "http 403",
                                   "could not")):
            pytest.skip(f"Transient failure for {source_name}: {e}")
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "net::err", "ssl", "nodename")):
            pytest.skip(f"Network/timeout for {source_name}: {e}")
        raise


@pytest.mark.integration
class TestAdresE2E:
    def test_afiliacion_salud(self):
        result = _safe_query("co.adres")
        print(f"\nADRES: {result}")


@pytest.mark.integration
class TestColpensionesE2E:
    def test_pension(self):
        result = _safe_query("co.colpensiones")
        print(f"\nColpensiones: {result}")


@pytest.mark.integration
class TestFopepE2E:
    def test_fopep(self):
        result = _safe_query("co.fopep")
        print(f"\nFOPEP: {result}")


@pytest.mark.integration
class TestRuafE2E:
    def test_ruaf(self):
        result = _safe_query("co.ruaf")
        print(f"\nRUAF: {result}")


@pytest.mark.integration
class TestRethusE2E:
    def test_rethus(self):
        result = _safe_query("co.rethus")
        print(f"\nRETHUS: {result}")


@pytest.mark.integration
class TestSoiE2E:
    def test_soi(self):
        result = _safe_query("co.soi")
        print(f"\nSOI: {result}")


@pytest.mark.integration
class TestSeguridadSocialE2E:
    def test_seguridad_social(self):
        result = _safe_query("co.seguridad_social")
        print(f"\nSeguridad Social: {result}")


@pytest.mark.integration
class TestAfiliadosCompensadoE2E:
    def test_compensacion(self):
        result = _safe_query("co.afiliados_compensado")
        print(f"\nAfiliados Compensado: {result}")


@pytest.mark.integration
class TestSisbenE2E:
    def test_sisben(self):
        result = _safe_query("co.sisben")
        print(f"\nSISBEN: {result}")
