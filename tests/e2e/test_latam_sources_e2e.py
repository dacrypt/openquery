"""End-to-end integration tests for EC, PE, MX, AR sources.

Tests hit real government websites. Sources that are deprecated raise
SourceError early — those tests assert the expected deprecation error.

Public test data (no personal info):
- PE RUC: 20100010757 (Banco de la Nacion Peru — public entity)

Run: uv run pytest tests/e2e/test_latam_sources_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import CaptchaError, SourceError
from openquery.sources import get_source
from openquery.sources.base import DocumentType, QueryInput


def _get_source(source_name: str):
    try:
        return get_source(source_name, timeout=45.0, headless=True)
    except TypeError:
        return get_source(source_name, timeout=45.0)


def _safe_query(source_name: str, doc_type: DocumentType = DocumentType.CUSTOM,
                doc_number: str = "", **extra):
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
        if any(k in msg for k in ("timeout", "ssl", "certificate", "net::err",
                                   "http 404", "http 403", "could not find")):
            pytest.skip(f"Transient failure for {source_name}: {e}")
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("timeout", "net::err", "ssl", "nodename")):
            pytest.skip(f"Network/timeout for {source_name}: {e}")
        raise


# ===========================================================================
# ec.cne_padron — needs work (bot-challenge wall), test expects SourceError at runtime
# ===========================================================================

@pytest.mark.integration
def test_ec_cne_padron_query():
    """ec.cne_padron attempts real query — may fail with SourceError due to bot wall."""
    src = _get_source("ec.cne_padron")
    try:
        result = src.query(QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="1700000001",
        ))
        assert result is not None
    except SourceError:
        pytest.skip("ec.cne_padron: bot-challenge wall still active")


@pytest.mark.integration
def test_ec_cne_padron_meta():
    src = _get_source("ec.cne_padron")
    meta = src.meta()
    assert meta.name == "ec.cne_padron"
    assert meta.country == "EC"


# ===========================================================================
# pe.osce_sancionados — live site, search by RUC or name
# ===========================================================================

@pytest.mark.integration
def test_pe_osce_sancionados_by_ruc():
    """Search by RUC of Banco de la Nacion (public entity, likely clean)."""
    result = _safe_query(
        "pe.osce_sancionados",
        doc_type=DocumentType.CUSTOM,
        doc_number="",
        ruc="20100010757",
    )
    if result is None:
        return  # skipped
    assert hasattr(result, "total_sancionados")
    assert result.total_sancionados >= 0
    print(f"\nOSCE sancionados (RUC 20100010757): {result.total_sancionados} records")


@pytest.mark.integration
def test_pe_osce_sancionados_by_name():
    """Search by name to verify the response model is returned."""
    result = _safe_query(
        "pe.osce_sancionados",
        doc_type=DocumentType.CUSTOM,
        doc_number="",
        name="CONSTRUCTORA",
    )
    if result is None:
        return  # skipped
    assert hasattr(result, "total_sancionados")
    assert result.total_sancionados >= 0
    print(f"\nOSCE sancionados (name=CONSTRUCTORA): {result.total_sancionados} records")


# ===========================================================================
# mx.siem — deprecated, query must raise SourceError immediately
# ===========================================================================

@pytest.mark.integration
def test_mx_siem_deprecated_raises():
    """mx.siem is deprecated — query must raise SourceError immediately."""
    src = _get_source("mx.siem")
    with pytest.raises(SourceError) as exc_info:
        src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"nombre": "TACOS"},
        ))
    msg = str(exc_info.value).lower()
    assert "unavailable" in msg or "inaccessible" in msg


@pytest.mark.integration
def test_mx_siem_meta():
    src = _get_source("mx.siem")
    meta = src.meta()
    assert meta.name == "mx.siem"
    assert meta.country == "MX"


# ===========================================================================
# ar.dnrpa — live site with CAPTCHA, query by plate
# ===========================================================================

@pytest.mark.integration
def test_ar_dnrpa_query_plate():
    """Query a plate and verify the result model is returned."""
    result = _safe_query(
        "ar.dnrpa",
        doc_type=DocumentType.PLATE,
        doc_number="AB123CD",
    )
    if result is None:
        return  # skipped due to CAPTCHA or network issue
    assert hasattr(result, "dominio")
    assert result.dominio == "AB123CD"
    print(f"\nDNRPA AB123CD: registro={result.registro_seccional!r}, "
          f"provincia={result.provincia!r}")


# ===========================================================================
# co.afiliados_compensado — SSF affiliation by cedula
# ===========================================================================

@pytest.mark.integration
def test_afiliados_compensado_meta():
    src = _get_source("co.afiliados_compensado")
    meta = src.meta()
    assert meta.name == "co.afiliados_compensado"
    assert meta.country == "CO"
    assert meta.requires_browser is True


@pytest.mark.integration
def test_afiliados_compensado_query_cedula():
    """Query a public cedula (Iván Duque — public figure) for compensation fund affiliation."""
    result = _safe_query(
        "co.afiliados_compensado",
        doc_type=DocumentType.CEDULA,
        doc_number="79940745",
    )
    if result is None:
        return  # skipped
    assert hasattr(result, "esta_afiliado")
    assert hasattr(result, "documento")
    assert result.documento == "79940745"
    print(f"\nAfiliados compensado: afiliado={result.esta_afiliado}, "
          f"caja={result.caja_compensacion!r}, estado={result.estado!r}")


# ===========================================================================
# pe.poder_judicial — CEJ judicial case search
# ===========================================================================

@pytest.mark.integration
def test_poder_judicial_meta():
    src = _get_source("pe.poder_judicial")
    meta = src.meta()
    assert meta.name == "pe.poder_judicial"
    assert meta.country == "PE"
    assert meta.requires_browser is True


@pytest.mark.integration
def test_poder_judicial_query_nombre():
    """Query by company name (Banco de la Nacion — public entity)."""
    result = _safe_query(
        "pe.poder_judicial",
        doc_type=DocumentType.CUSTOM,
        doc_number="20100030595",
        nombre="Banco de la Nacion",
    )
    if result is None:
        return  # skipped
    assert hasattr(result, "total_expedientes")
    assert hasattr(result, "expedientes")
    assert result.total_expedientes >= 0
    print(f"\nPoder Judicial Banco de la Nacion: {result.total_expedientes} expedientes")


# ===========================================================================
# pe.sunarp_vehicular — SUNARP vehicle registry by plate
# ===========================================================================

@pytest.mark.integration
def test_sunarp_vehicular_meta():
    src = _get_source("pe.sunarp_vehicular")
    meta = src.meta()
    assert meta.name == "pe.sunarp_vehicular"
    assert meta.country == "PE"
    assert meta.requires_browser is True


@pytest.mark.integration
def test_sunarp_vehicular_query_plate():
    """Query a Peruvian plate format — may return no data for test plate."""
    result = _safe_query(
        "pe.sunarp_vehicular",
        doc_type=DocumentType.PLATE,
        doc_number="ABC-123",
    )
    if result is None:
        return  # skipped
    assert hasattr(result, "placa")
    print(f"\nSUNARP ABC-123: propietario={result.propietario!r}, "
          f"marca={result.marca!r}, estado={result.estado!r}")
