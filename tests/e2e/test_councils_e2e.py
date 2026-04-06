"""End-to-end tests for professional council sources (browser-based).

These sources query various Colombian professional councils to check
if a person is registered. Most people won't be registered in most
councils, so "not found" is a valid result.

Public test data:
- Cedula: 79940745 (Iván Duque, ex-president — public SIGEP record)

Run: uv run pytest tests/e2e/test_councils_e2e.py -v -s -m integration
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


def _safe_query(source_name: str):
    """Query a council source, skip on CAPTCHA/timeout."""
    src = _get_source(source_name)
    try:
        return src.query(
            QueryInput(
                document_type=DocumentType.CEDULA,
                document_number=CEDULA_PUBLIC,
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
        if "no se encontr" in msg or "no registra" in msg or "sin resultado" in msg:
            print(f"\n{source_name}: Not registered (expected)")
            return None
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "net::err", "ssl", "nodename")):
            pytest.skip(f"Network/timeout for {source_name}: {e}")
        raise


COUNCIL_SOURCES = [
    "co.copnia",
    "co.conaltel",
    "co.consejo_mecanica",
    "co.cpae",
    "co.cpip",
    "co.cpiq",
    "co.cpnaa",
    "co.cpnt",
    "co.cpbiol",
    "co.veterinario",
    "co.urna",
]


@pytest.mark.integration
@pytest.mark.parametrize("source_name", COUNCIL_SOURCES)
def test_council_source(source_name: str):
    """Each council source should return data or 'not found' without crashing."""
    result = _safe_query(source_name)
    if result is not None:
        print(f"\n{source_name}: {result}")
    # If result is None, _safe_query already printed "Not registered"
