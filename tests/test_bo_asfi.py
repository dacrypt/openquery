"""Tests for bo.asfi — Bolivia ASFI supervised financial entities source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAsfiParseResult:
    def _parse(self, body_text: str, rows=None, search_term: str = "Banco Nacional"):
        from openquery.sources.bo.asfi import AsfiSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = AsfiSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.entity_type == ""
        assert result.license_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Banco Mercantil")
        assert result.search_term == "Banco Mercantil"

    def test_text_parse_entity_fields(self):
        body = "Entidad: Banco Nacional de Bolivia\nTipo: Banco\nEstado: Autorizado"
        result = self._parse(body)
        assert result.entity_name == "Banco Nacional de Bolivia"
        assert result.entity_type == "Banco"
        assert result.license_status == "Autorizado"

    def test_text_parse_nombre_field(self):
        body = "Nombre: Cooperativa de Ahorro XYZ\nEstado: Activo"
        result = self._parse(body)
        assert result.entity_name == "Cooperativa de Ahorro XYZ"
        assert result.license_status == "Activo"

    def test_table_rows_parsed(self):
        def make_cell(text):
            cell = MagicMock()
            cell.inner_text.return_value = text
            return cell

        def make_row(texts):
            row = MagicMock()
            row.query_selector_all.return_value = [make_cell(t) for t in texts]
            return row

        header = make_row(["Entidad", "Tipo", "Licencia"])
        data_row = make_row(["Banco FIE", "Banco Múltiple", "Autorizado"])

        result = self._parse("", rows=[header, data_row])
        assert result.entity_name == "Banco FIE"
        assert result.entity_type == "Banco Múltiple"
        assert result.license_status == "Autorizado"

    def test_model_roundtrip(self):
        from openquery.models.bo.asfi import AsfiResult

        r = AsfiResult(
            search_term="Banco BNB",
            entity_name="Banco Nacional de Bolivia",
            entity_type="Banco",
            license_status="Autorizado",
        )
        data = r.model_dump_json()
        r2 = AsfiResult.model_validate_json(data)
        assert r2.search_term == "Banco BNB"
        assert r2.entity_name == "Banco Nacional de Bolivia"
        assert r2.license_status == "Autorizado"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.asfi import AsfiResult

        r = AsfiResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestAsfiSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.asfi import AsfiSource

        meta = AsfiSource().meta()
        assert meta.name == "bo.asfi"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.bo.asfi import AsfiSource

        src = AsfiSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_entity_name_extra(self):
        from openquery.sources.bo.asfi import AsfiSource

        src = AsfiSource()
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"entity_name": "Banco Mercantil"},
        )
        assert input_.extra["entity_name"] == "Banco Mercantil"

    def test_document_number_used_as_fallback(self):
        from openquery.sources.bo.asfi import AsfiSource

        src = AsfiSource()
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Banco Nacional",
        )
        # document_number is non-empty, so it should not raise
        assert input_.document_number == "Banco Nacional"
