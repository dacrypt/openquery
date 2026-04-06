"""Tests for cr.hacienda — Costa Rica Hacienda tax declarant status lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.cr.hacienda import CrHaciendaResult
from openquery.sources.base import DocumentType, QueryInput


class TestCrHaciendaResult:
    """Model default values, JSON roundtrip, audit exclusion."""

    def test_defaults(self):
        r = CrHaciendaResult()
        assert r.cedula == ""
        assert r.declarant_status == ""
        assert r.obligations == ""
        assert r.details == ""
        assert r.audit is None

    def test_queried_at_default(self):
        r = CrHaciendaResult()
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        r = CrHaciendaResult(
            cedula="1-0234-0567",
            declarant_status="Declarante Activo",
            obligations="Renta, IVA",
        )
        restored = CrHaciendaResult.model_validate_json(r.model_dump_json())
        assert restored.cedula == "1-0234-0567"
        assert restored.declarant_status == "Declarante Activo"
        assert restored.obligations == "Renta, IVA"

    def test_audit_excluded_from_json(self):
        r = CrHaciendaResult(cedula="1-0234-0567", audit=b"pdf-data")
        dumped = r.model_dump_json()
        assert "audit" not in dumped

    def test_audit_excluded_from_dict(self):
        r = CrHaciendaResult(cedula="1-0234-0567", audit={"key": "val"})
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestCrHaciendaSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.hacienda import CrHaciendaSource

        meta = CrHaciendaSource().meta()
        assert meta.name == "cr.hacienda"
        assert meta.country == "CR"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10

    def test_missing_cedula_raises(self):
        from openquery.sources.cr.hacienda import CrHaciendaSource

        src = CrHaciendaSource()
        with pytest.raises(SourceError, match="Cédula is required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))


class TestCrHaciendaParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, cedula: str = "1-0234-0567") -> CrHaciendaResult:
        from openquery.sources.cr.hacienda import CrHaciendaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CrHaciendaSource()
        return src._parse_result(page, cedula)

    def test_cedula_preserved(self):
        result = self._parse("Sin resultados", cedula="3-0456-0789")
        assert result.cedula == "3-0456-0789"

    def test_parses_estado(self):
        body = "Estado: Declarante Activo\n"
        result = self._parse(body)
        assert result.declarant_status == "Declarante Activo"

    def test_parses_condicion(self):
        body = "Condición: No Declarante\n"
        result = self._parse(body)
        assert result.declarant_status == "No Declarante"

    def test_parses_condicion_without_accent(self):
        body = "Condicion: Declarante Inactivo\n"
        result = self._parse(body)
        assert result.declarant_status == "Declarante Inactivo"

    def test_parses_declarante(self):
        body = "Declarante: Sí\n"
        result = self._parse(body)
        assert result.declarant_status == "Sí"

    def test_parses_obligacion_with_accent(self):
        body = "Obligación: Impuesto sobre la Renta\n"
        result = self._parse(body)
        assert result.obligations == "Impuesto sobre la Renta"

    def test_parses_obligacion_without_accent(self):
        body = "Obligacion: IVA\n"
        result = self._parse(body)
        assert result.obligations == "IVA"

    def test_parses_obligaciones(self):
        body = "Obligaciones: Renta, IVA, Timbre\n"
        result = self._parse(body)
        assert result.obligations == "Renta, IVA, Timbre"

    def test_parses_impuesto(self):
        body = "Impuesto: Renta\n"
        result = self._parse(body)
        assert result.obligations == "Renta"

    def test_parses_tributo(self):
        body = "Tributo: IVA\n"
        result = self._parse(body)
        assert result.obligations == "IVA"

    def test_details_truncated_to_500(self):
        body = "Y" * 1000
        result = self._parse(body)
        assert len(result.details) == 500

    def test_empty_body(self):
        result = self._parse("")
        assert result.declarant_status == ""
        assert result.obligations == ""

    def test_multiple_fields_parsed(self):
        body = "Estado: Declarante Activo\nObligaciones: Renta, IVA\n"
        result = self._parse(body)
        assert result.declarant_status == "Declarante Activo"
        assert result.obligations == "Renta, IVA"
