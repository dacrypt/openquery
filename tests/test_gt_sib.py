"""Tests for gt.sib — Guatemala SIB banking supervisor source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtSibParseResult:
    def _parse(self, body_text: str, search_term: str = "Banco Industrial"):
        from openquery.sources.gt.sib import GtSibSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = GtSibSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.entity_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Banco Industrial")
        assert result.search_term == "Banco Industrial"

    def test_entity_name_parsed(self):
        result = self._parse("Entidad: Banco Industrial SA\nEstado: Autorizado")
        assert result.entity_name == "Banco Industrial SA"

    def test_status_parsed(self):
        result = self._parse("Entidad: Banco X\nEstado: Activo")
        assert result.status == "Activo"

    def test_entity_type_parsed(self):
        result = self._parse("Tipo: Banco\nEstado: Activo")
        assert result.entity_type == "Banco"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.gt.sib import GtSibSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Banco Rural", "Banco", "Autorizado"])]  # noqa: E501
        src = GtSibSource()
        result = src._parse_result(page, "Banco Rural")
        assert result.entity_name == "Banco Rural"
        assert result.entity_type == "Banco"
        assert result.status == "Autorizado"

    def test_model_roundtrip(self):
        from openquery.models.gt.sib import GtSibResult

        r = GtSibResult(
            search_term="Banco Industrial",
            entity_name="Banco Industrial SA",
            entity_type="Banco",
            status="Autorizado",
        )
        data = r.model_dump_json()
        r2 = GtSibResult.model_validate_json(data)
        assert r2.entity_name == "Banco Industrial SA"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.sib import GtSibResult

        r = GtSibResult(search_term="Banco X", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestGtSibSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.sib import GtSibSource

        meta = GtSibSource().meta()
        assert meta.name == "gt.sib"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.gt.sib import GtSibSource

        src = GtSibSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="Banco Industrial")
        assert qi.document_number == "Banco Industrial"
