"""Tests for bo.senapi — Bolivia SENAPI trademark/patent registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSenapiParseResult:
    def _parse(self, body_text: str, rows=None, search_term: str = "SAMSUNG"):
        from openquery.sources.bo.senapi import SenapiSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = SenapiSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.trademark_name == ""
        assert result.owner == ""
        assert result.status == ""
        assert result.registration_date == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="COCA COLA")
        assert result.search_term == "COCA COLA"

    def test_text_parse_trademark_fields(self):
        body = (
            "Marca: SAMSUNG\nTitular: Samsung Electronics Co.\n"
            "Estado: Registrada\nFecha: 2015-03-10"
        )
        result = self._parse(body)
        assert result.trademark_name == "SAMSUNG"
        assert result.owner == "Samsung Electronics Co."
        assert result.status == "Registrada"
        assert result.registration_date == "2015-03-10"

    def test_text_parse_nombre_field(self):
        body = "Nombre: COCA COLA\nPropietario: The Coca-Cola Company\nEstado: Vigente"
        result = self._parse(body)
        assert result.trademark_name == "COCA COLA"
        assert result.owner == "The Coca-Cola Company"
        assert result.status == "Vigente"

    def test_table_rows_parsed(self):
        def make_cell(text):
            cell = MagicMock()
            cell.inner_text.return_value = text
            return cell

        def make_row(texts):
            row = MagicMock()
            row.query_selector_all.return_value = [make_cell(t) for t in texts]
            return row

        header = make_row(["Marca", "Titular", "Estado", "Fecha"])
        data_row = make_row(["NIKE", "Nike Inc.", "Registrada", "2010-06-01"])

        result = self._parse("", rows=[header, data_row])
        assert result.trademark_name == "NIKE"
        assert result.owner == "Nike Inc."
        assert result.status == "Registrada"
        assert result.registration_date == "2010-06-01"

    def test_model_roundtrip(self):
        from openquery.models.bo.senapi import SenapiResult

        r = SenapiResult(
            search_term="SAMSUNG",
            trademark_name="SAMSUNG",
            owner="Samsung Electronics",
            status="Registrada",
            registration_date="2015-03-10",
        )
        data = r.model_dump_json()
        r2 = SenapiResult.model_validate_json(data)
        assert r2.search_term == "SAMSUNG"
        assert r2.trademark_name == "SAMSUNG"
        assert r2.owner == "Samsung Electronics"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.senapi import SenapiResult

        r = SenapiResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSenapiSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.senapi import SenapiSource

        meta = SenapiSource().meta()
        assert meta.name == "bo.senapi"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.bo.senapi import SenapiSource

        src = SenapiSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_trademark_name_extra(self):
        from openquery.sources.bo.senapi import SenapiSource

        src = SenapiSource()
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"trademark_name": "SAMSUNG"},
        )
        assert input_.extra["trademark_name"] == "SAMSUNG"

    def test_document_number_used_as_fallback(self):
        from openquery.sources.bo.senapi import SenapiSource

        src = SenapiSource()
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="ADIDAS",
        )
        assert input_.document_number == "ADIDAS"
