"""Tests for ve.saime — Venezuela SAIME cedula filiatory data source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSaimeParseResult:
    def _parse(self, body_text: str, rows=None, cedula: str = "V12345678"):
        from openquery.sources.ve.saime import SaimeSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = SaimeSource()
        return src._parse_result(page, cedula)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.document_status == ""

    def test_cedula_preserved(self):
        result = self._parse("", cedula="V98765432")
        assert result.cedula == "V98765432"

    def test_text_parse_nombre_and_status(self):
        body = "Nombres: JUAN CARLOS\nApellidos: PEREZ GARCIA\nEstado: Vigente"
        result = self._parse(body)
        assert result.nombre == "JUAN CARLOS"
        assert result.document_status == "Vigente"

    def test_text_parse_vigencia_field(self):
        body = "Nombre: MARIA LOPEZ\nVigencia: Vencida"
        result = self._parse(body)
        assert result.nombre == "MARIA LOPEZ"
        assert result.document_status == "Vencida"

    def test_table_row_fallback(self):
        def make_row(text):
            row = MagicMock()
            row.inner_text.return_value = text
            return row

        rows = [
            make_row("Nombre: CARLOS RODRIGUEZ"),
            make_row("Estado: Activo"),
        ]
        result = self._parse("", rows=rows)
        assert result.nombre == "CARLOS RODRIGUEZ"
        assert result.document_status == "Activo"

    def test_model_roundtrip(self):
        from openquery.models.ve.saime import SaimeResult

        r = SaimeResult(
            cedula="V12345678",
            nombre="JUAN PEREZ",
            document_status="Vigente",
        )
        data = r.model_dump_json()
        r2 = SaimeResult.model_validate_json(data)
        assert r2.cedula == "V12345678"
        assert r2.nombre == "JUAN PEREZ"
        assert r2.document_status == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.saime import SaimeResult

        r = SaimeResult(cedula="V12345678", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSaimeSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.saime import SaimeSource

        meta = SaimeSource().meta()
        assert meta.name == "ve.saime"
        assert meta.country == "VE"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_cedula_raises(self):
        from openquery.sources.ve.saime import SaimeSource

        src = SaimeSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.ve.saime import SaimeSource

        src = SaimeSource()
        with pytest.raises(SourceError, match="Unsupported"):
            src.query(QueryInput(document_type=DocumentType.NIT, document_number="12345"))

    def test_details_populated(self):
        from openquery.sources.ve.saime import SaimeSource

        page = MagicMock()
        page.inner_text.return_value = "Fecha Nacimiento: 1990-05-20\nEstado: Vigente"
        page.query_selector_all.return_value = []
        src = SaimeSource()
        result = src._parse_result(page, "V12345678")
        assert "Fecha Nacimiento" in result.details
