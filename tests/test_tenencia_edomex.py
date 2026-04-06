"""Unit tests for mx.tenencia_edomex — Estado de Mexico vehicle tenencia tax."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openquery.models.mx.tenencia_edomex import TenenciaEdomexResult
from openquery.sources.mx.tenencia_edomex import TenenciaEdomexSource

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestTenenciaEdomexResult:
    def test_default_values(self):
        r = TenenciaEdomexResult()
        assert r.placa == ""
        assert r.tenencia_amount == ""
        assert r.payment_status == ""
        assert r.vehicle_description == ""
        assert r.details == ""
        assert r.audit is None

    def test_round_trip(self):
        r = TenenciaEdomexResult(
            placa="ABC1234",
            tenencia_amount="$1,500.00",
            payment_status="Pendiente",
            vehicle_description="Sedan 2020",
        )
        restored = TenenciaEdomexResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC1234"
        assert restored.tenencia_amount == "$1,500.00"
        assert restored.payment_status == "Pendiente"
        assert restored.vehicle_description == "Sedan 2020"

    def test_audit_excluded(self):
        r = TenenciaEdomexResult(placa="ABC1234")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_json_audit_excluded(self):
        r = TenenciaEdomexResult(placa="XYZ9999")
        r.audit = b"pdf_bytes"
        data = json.loads(r.model_dump_json())
        assert "audit" not in data


# ---------------------------------------------------------------------------
# Source meta tests
# ---------------------------------------------------------------------------


class TestTenenciaEdomexSourceMeta:
    def test_meta(self):
        src = TenenciaEdomexSource()
        meta = src.meta()
        assert meta.name == "mx.tenencia_edomex"
        assert meta.country == "MX"
        assert meta.requires_captcha is True
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_display_name(self):
        src = TenenciaEdomexSource()
        meta = src.meta()
        assert "Tenencia" in meta.display_name or "SFPYA" in meta.display_name

    def test_url(self):
        src = TenenciaEdomexSource()
        meta = src.meta()
        assert "edomexico.gob.mx" in meta.url

    def test_supported_inputs(self):
        from openquery.sources.base import DocumentType

        src = TenenciaEdomexSource()
        meta = src.meta()
        assert DocumentType.PLATE in meta.supported_inputs


# ---------------------------------------------------------------------------
# Parse result tests
# ---------------------------------------------------------------------------


class TestTenenciaEdomexParseResult:
    def test_parse_paid_status(self):
        page = MagicMock()
        page.inner_text.return_value = (
            "Placa: ABC1234\nEstatus: Pagado\nTenencia: $1,500.00\n"
        )

        src = TenenciaEdomexSource()
        result = src._parse_result(page, "ABC1234")

        assert result.placa == "ABC1234"
        assert result.payment_status == "Pagado"
        assert "$1,500.00" in result.tenencia_amount

    def test_parse_pending_status(self):
        page = MagicMock()
        page.inner_text.return_value = (
            "Placa: XYZ9999\nEstatus: Pendiente de pago\nAdeudo: $2,200.00\n"
        )

        src = TenenciaEdomexSource()
        result = src._parse_result(page, "XYZ9999")

        assert result.placa == "XYZ9999"
        assert result.payment_status == "Pendiente"

    def test_parse_not_found(self):
        page = MagicMock()
        page.inner_text.return_value = "La placa no existe en el sistema."

        src = TenenciaEdomexSource()
        result = src._parse_result(page, "ZZZ0000")

        assert result.placa == "ZZZ0000"
        assert result.payment_status == "No encontrado"

    def test_parse_amount_extracted(self):
        page = MagicMock()
        page.inner_text.return_value = "Monto a pagar: $3,750.50\nEstatus: Pendiente"

        src = TenenciaEdomexSource()
        result = src._parse_result(page, "TEST123")

        assert result.tenencia_amount == "$3,750.50"

    def test_parse_details_truncated(self):
        page = MagicMock()
        long_text = "A" * 1000
        page.inner_text.return_value = long_text

        src = TenenciaEdomexSource()
        result = src._parse_result(page, "ABC1234")

        assert len(result.details) <= 500
