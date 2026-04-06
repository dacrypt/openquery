"""Tests for sv.hacienda — El Salvador Hacienda DUI/NIT source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvHaciendaParseResult:
    def _parse(self, body_text: str, dui: str = "00000000-0"):
        from openquery.sources.sv.hacienda import SvHaciendaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SvHaciendaSource()
        return src._parse_result(page, dui)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nit == ""
        assert result.taxpayer_status == ""

    def test_dui_preserved(self):
        result = self._parse("", dui="00000000-0")
        assert result.dui == "00000000-0"

    def test_nit_parsed(self):
        result = self._parse("NIT: 0614-000000-000-0\nEstado: Activo")
        assert result.nit == "0614-000000-000-0"

    def test_taxpayer_status_parsed_estado(self):
        result = self._parse("Estado: Activo\nNIT: 0614-000000-000-0")
        assert result.taxpayer_status == "Activo"

    def test_taxpayer_status_parsed_situacion(self):
        result = self._parse("Situación: Contribuyente Activo")
        assert result.taxpayer_status == "Contribuyente Activo"

    def test_details_populated(self):
        result = self._parse("NIT: 0614-000000-000-0\nEstado: Activo")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.sv.hacienda import SvHaciendaResult

        r = SvHaciendaResult(
            dui="00000000-0",
            nit="0614-000000-000-0",
            taxpayer_status="Activo",
        )
        data = r.model_dump_json()
        r2 = SvHaciendaResult.model_validate_json(data)
        assert r2.dui == "00000000-0"
        assert r2.nit == "0614-000000-000-0"
        assert r2.taxpayer_status == "Activo"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.hacienda import SvHaciendaResult

        r = SvHaciendaResult(dui="00000000-0", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvHaciendaSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.hacienda import SvHaciendaSource

        meta = SvHaciendaSource().meta()
        assert meta.name == "sv.hacienda"
        assert meta.country == "SV"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dui_raises(self):
        from openquery.sources.sv.hacienda import SvHaciendaSource

        src = SvHaciendaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_dui_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="",
            extra={"dui": "00000000-0"},
        )
        assert inp.extra.get("dui") == "00000000-0"

    def test_dui_from_document_number(self):
        inp = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="00000000-0",
        )
        assert inp.document_number == "00000000-0"
