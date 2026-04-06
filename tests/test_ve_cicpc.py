"""Tests for ve.cicpc — Venezuela CICPC criminal records source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCicpcParseResult:
    def _parse(self, body_text: str, rows=None, cedula: str = "V12345678"):
        from openquery.sources.ve.cicpc import CicpcSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = CicpcSource()
        return src._parse_result(page, cedula)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.criminal_status == ""
        assert result.details == {}

    def test_cedula_preserved(self):
        result = self._parse("", cedula="V87654321")
        assert result.cedula == "V87654321"

    def test_text_parse_antecedente_field(self):
        body = "Antecedentes: Sin antecedentes penales"
        result = self._parse(body)
        assert result.criminal_status == "Sin antecedentes penales"

    def test_text_parse_resultado_field(self):
        body = "Resultado: No registra antecedentes"
        result = self._parse(body)
        assert result.criminal_status == "No registra antecedentes"

    def test_text_parse_estado_field(self):
        body = "Estado: Limpio"
        result = self._parse(body)
        assert result.criminal_status == "Limpio"

    def test_table_row_fallback(self):
        def make_row(text):
            row = MagicMock()
            row.inner_text.return_value = text
            return row

        rows = [
            make_row("Antecedentes: Sin registros"),
        ]
        result = self._parse("", rows=rows)
        assert result.criminal_status == "Sin registros"

    def test_details_populated(self):
        body = "Antecedentes: Ninguno\nFecha Consulta: 2024-01-15"
        result = self._parse(body)
        assert "Antecedentes" in result.details
        assert "Fecha Consulta" in result.details

    def test_model_roundtrip(self):
        from openquery.models.ve.cicpc import CicpcResult

        r = CicpcResult(
            cedula="V12345678",
            criminal_status="Sin antecedentes",
        )
        data = r.model_dump_json()
        r2 = CicpcResult.model_validate_json(data)
        assert r2.cedula == "V12345678"
        assert r2.criminal_status == "Sin antecedentes"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.cicpc import CicpcResult

        r = CicpcResult(cedula="V12345678", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestCicpcSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.cicpc import CicpcSource

        meta = CicpcSource().meta()
        assert meta.name == "ve.cicpc"
        assert meta.country == "VE"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_cedula_raises(self):
        from openquery.sources.ve.cicpc import CicpcSource

        src = CicpcSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.ve.cicpc import CicpcSource

        src = CicpcSource()
        with pytest.raises(SourceError, match="Unsupported"):
            src.query(QueryInput(document_type=DocumentType.NIT, document_number="12345"))
