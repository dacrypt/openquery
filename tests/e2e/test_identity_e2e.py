"""End-to-end tests for identity & antecedentes sources (browser-based).

These sources use Playwright to scrape government websites.
Require: network access, Playwright + Chromium, possibly OCR.

Public test data:
- Cedula: 79940745 (Iván Duque, ex-president — public SIGEP record)

Run: uv run pytest tests/e2e/test_identity_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import CaptchaError, SourceError
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput

CEDULA_PUBLIC = "79940745"  # Iván Duque — ex-president


def _get_source(name: str):
    try:
        return get_source(name, timeout=45.0, headless=True)
    except TypeError:
        return get_source(name, timeout=45.0)


def _query(source_name: str, doc_type: DocumentType = DocumentType.CEDULA,
           doc_number: str = CEDULA_PUBLIC, **extra):
    src = _get_source(source_name)
    return src.query(QueryInput(
        document_type=doc_type,
        document_number=doc_number,
        extra=extra,
    ))


def _safe_query(source_name: str, **kwargs):
    """Run query, skip on transient failures (CAPTCHA, timeouts, network)."""
    try:
        return _query(source_name, **kwargs)
    except CaptchaError as e:
        pytest.skip(f"CAPTCHA failed for {source_name}: {e}")
    except SourceError as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "navegación", "ssl", "certificate",
                                   "http 404", "http 403", "could not",
                                   "deprecated")):
            pytest.skip(f"Transient failure for {source_name}: {e}")
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "net::err", "ssl", "nodename")):
            pytest.skip(f"Network/timeout for {source_name}: {e}")
        raise


# ===========================================================================
# Identity & civil registry
# ===========================================================================
@pytest.mark.integration
class TestEstadoCedulaE2E:
    def test_cedula_status(self):
        result = _safe_query("co.estado_cedula")
        assert result is not None
        print(f"\nEstado Cédula: {result}")


@pytest.mark.integration
class TestEstadoTramiteCedulaE2E:
    def test_tramite_status(self):
        result = _safe_query("co.estado_tramite_cedula")
        print(f"\nEstado Trámite Cédula: {result}")


@pytest.mark.integration
class TestNombreCompletoE2E:
    def test_nombre(self):
        result = _safe_query("co.nombre_completo")
        print(f"\nNombre Completo: {result}")


@pytest.mark.integration
class TestDefuncionE2E:
    def test_vigencia(self):
        result = _safe_query("co.defuncion")
        print(f"\nDefunción (vigencia): {result}")


@pytest.mark.integration
class TestPuestoVotacionE2E:
    def test_puesto(self):
        result = _safe_query("co.puesto_votacion")
        print(f"\nPuesto Votación: {result}")


@pytest.mark.integration
class TestRegistroCivilE2E:
    def test_registro(self):
        result = _safe_query("co.registro_civil")
        print(f"\nRegistro Civil: {result}")


@pytest.mark.integration
class TestLibretaMilitarE2E:
    def test_libreta(self):
        result = _safe_query("co.libreta_militar")
        print(f"\nLibreta Militar: {result}")


# ===========================================================================
# Antecedentes & justice
# ===========================================================================
@pytest.mark.integration
class TestPoliciaE2E:
    def test_antecedentes(self):
        result = _safe_query("co.policia")
        print(f"\nPolicía antecedentes: {result}")


@pytest.mark.integration
class TestProcuraduriaE2E:
    def test_disciplinarios(self):
        result = _safe_query("co.procuraduria")
        print(f"\nProcuraduría: {result}")


@pytest.mark.integration
class TestContraloriaE2E:
    def test_fiscal(self):
        result = _safe_query("co.contraloria")
        print(f"\nContraloría: {result}")


@pytest.mark.integration
class TestRnmcE2E:
    def test_medidas_correctivas(self):
        result = _safe_query("co.rnmc")
        print(f"\nRNMC: {result}")


@pytest.mark.integration
class TestConsultaProcesosE2E:
    def test_procesos(self):
        result = _safe_query("co.consulta_procesos")
        print(f"\nConsulta Procesos: {result}")


@pytest.mark.integration
class TestTutelasE2E:
    def test_tutelas(self):
        result = _safe_query("co.tutelas")
        print(f"\nTutelas: {result}")


@pytest.mark.integration
class TestJepE2E:
    def test_jep(self):
        result = _safe_query("co.jep")
        print(f"\nJEP: {result}")


@pytest.mark.integration
class TestInpecE2E:
    def test_inpec(self):
        result = _safe_query("co.inpec")
        print(f"\nINPEC: {result}")
