"""Unit tests for mx.verificacion_cdmx — CDMX emissions verification status."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openquery.models.mx.verificacion_cdmx import VerificacionCdmxResult
from openquery.sources.mx.verificacion_cdmx import VerificacionCdmxSource

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestVerificacionCdmxResult:
    def test_default_values(self):
        r = VerificacionCdmxResult()
        assert r.placa == ""
        assert r.hologram_type == ""
        assert r.exemption_status == ""
        assert r.validity_semester == ""
        assert r.details == ""
        assert r.audit is None

    def test_round_trip(self):
        r = VerificacionCdmxResult(
            placa="ABC1234",
            hologram_type="0",
            exemption_status="Exento",
            validity_semester="1er semestre 2025",
        )
        restored = VerificacionCdmxResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "ABC1234"
        assert restored.hologram_type == "0"
        assert restored.exemption_status == "Exento"
        assert restored.validity_semester == "1er semestre 2025"

    def test_audit_excluded(self):
        r = VerificacionCdmxResult(placa="ABC1234")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_json_audit_excluded(self):
        r = VerificacionCdmxResult(placa="XYZ9999")
        r.audit = b"pdf_bytes"
        data = json.loads(r.model_dump_json())
        assert "audit" not in data


# ---------------------------------------------------------------------------
# Source meta tests
# ---------------------------------------------------------------------------


class TestVerificacionCdmxSourceMeta:
    def test_meta(self):
        src = VerificacionCdmxSource()
        meta = src.meta()
        assert meta.name == "mx.verificacion_cdmx"
        assert meta.country == "MX"
        assert meta.requires_captcha is False
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_display_name(self):
        src = VerificacionCdmxSource()
        meta = src.meta()
        assert "Verificac" in meta.display_name or "SEDEMA" in meta.display_name

    def test_url(self):
        src = VerificacionCdmxSource()
        meta = src.meta()
        assert "sedema.cdmx.gob.mx" in meta.url

    def test_supported_inputs(self):
        from openquery.sources.base import DocumentType

        src = VerificacionCdmxSource()
        meta = src.meta()
        assert DocumentType.PLATE in meta.supported_inputs


# ---------------------------------------------------------------------------
# Parse result tests
# ---------------------------------------------------------------------------


class TestVerificacionCdmxParseResult:
    def test_parse_hologram_0(self):
        page = MagicMock()
        page.inner_text.return_value = "Placa: ABC1234\nHolograma: 0\nExento de verificar"

        src = VerificacionCdmxSource()
        result = src._parse_result(page, "ABC1234")

        assert result.placa == "ABC1234"
        assert result.hologram_type in ("0", "00")

    def test_parse_hologram_explicit(self):
        page = MagicMock()
        page.inner_text.return_value = "Resultado: Holograma 2\nVigencia: 2do semestre 2025"

        src = VerificacionCdmxSource()
        result = src._parse_result(page, "XYZ9999")

        assert result.hologram_type == "2"

    def test_parse_exemption_exento(self):
        page = MagicMock()
        page.inner_text.return_value = "Vehículo exento de verificación\nSemestre: 1er semestre 2025"  # noqa: E501

        src = VerificacionCdmxSource()
        result = src._parse_result(page, "EXE1234")

        assert result.exemption_status == "Exento"

    def test_parse_validity_semester(self):
        page = MagicMock()
        page.inner_text.return_value = "Vigencia: 2do semestre 2025\nHolograma: 1"

        src = VerificacionCdmxSource()
        result = src._parse_result(page, "SEM1234")

        assert "semestre" in result.validity_semester.lower() or "2025" in result.validity_semester

    def test_parse_details_populated(self):
        page = MagicMock()
        page.inner_text.return_value = "Información del vehículo: datos de verificación disponibles."  # noqa: E501

        src = VerificacionCdmxSource()
        result = src._parse_result(page, "ABC1234")

        assert result.details != ""
        assert len(result.details) <= 500
