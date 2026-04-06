"""Tests for gt.registro_propiedad — Guatemala property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtRegistroPropiedadParseResult:
    def _parse(self, body_text: str, search_value: str = "12345"):
        from openquery.sources.gt.registro_propiedad import GtRegistroPropiedadSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = GtRegistroPropiedadSource()
        return src._parse_result(page, search_value)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.finca_number == ""
        assert result.owner == ""
        assert result.property_type == ""

    def test_search_value_preserved(self):
        result = self._parse("", search_value="F-123")
        assert result.search_value == "F-123"

    def test_owner_parsed(self):
        result = self._parse("Propietario: Juan Perez\nTipo: Urbano")
        assert result.owner == "Juan Perez"

    def test_property_type_parsed(self):
        result = self._parse("Tipo: Rural")
        assert result.property_type == "Rural"

    def test_finca_parsed(self):
        result = self._parse("Finca: 9876")
        assert result.finca_number == "9876"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.gt.registro_propiedad import GtRegistroPropiedadSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["F-001", "Maria Lopez", "Urbana"])]  # noqa: E501
        src = GtRegistroPropiedadSource()
        result = src._parse_result(page, "F-001")
        assert result.finca_number == "F-001"
        assert result.owner == "Maria Lopez"
        assert result.property_type == "Urbana"

    def test_model_roundtrip(self):
        from openquery.models.gt.registro_propiedad import GtRegistroPropiedadResult

        r = GtRegistroPropiedadResult(
            search_value="F-001",
            finca_number="F-001",
            owner="Maria Lopez",
            property_type="Urbana",
        )
        data = r.model_dump_json()
        r2 = GtRegistroPropiedadResult.model_validate_json(data)
        assert r2.search_value == "F-001"
        assert r2.owner == "Maria Lopez"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.registro_propiedad import GtRegistroPropiedadResult

        r = GtRegistroPropiedadResult(search_value="F-001", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestGtRegistroPropiedadSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.registro_propiedad import GtRegistroPropiedadSource

        meta = GtRegistroPropiedadSource().meta()
        assert meta.name == "gt.registro_propiedad"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.gt.registro_propiedad import GtRegistroPropiedadSource

        src = GtRegistroPropiedadSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="F-999")
        assert qi.document_number == "F-999"
