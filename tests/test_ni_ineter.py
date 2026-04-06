"""Tests for ni.ineter — Nicaragua INETER cadastro source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiIneterParseResult:
    def _parse(self, body_text: str, search_value: str = "CAT-001"):
        from openquery.sources.ni.ineter import NiIneterSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = NiIneterSource()
        return src._parse_result(page, search_value)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.property_code == ""
        assert result.owner == ""
        assert result.location == ""

    def test_search_value_preserved(self):
        result = self._parse("", search_value="CAT-001")
        assert result.search_value == "CAT-001"

    def test_owner_parsed(self):
        result = self._parse("Propietario: Juan Garcia\nUbicacion: Managua")
        assert result.owner == "Juan Garcia"

    def test_location_parsed(self):
        result = self._parse("Ubicacion: Managua, Nicaragua")
        assert result.location == "Managua, Nicaragua"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.ni.ineter import NiIneterSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["NI-999", "Pedro Lopez", "Masaya"])]  # noqa: E501
        src = NiIneterSource()
        result = src._parse_result(page, "NI-999")
        assert result.property_code == "NI-999"
        assert result.owner == "Pedro Lopez"
        assert result.location == "Masaya"

    def test_model_roundtrip(self):
        from openquery.models.ni.ineter import NiIneterResult

        r = NiIneterResult(
            search_value="CAT-001",
            property_code="CAT-001",
            owner="Pedro Lopez",
            location="Managua",
        )
        data = r.model_dump_json()
        r2 = NiIneterResult.model_validate_json(data)
        assert r2.owner == "Pedro Lopez"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.ineter import NiIneterResult

        r = NiIneterResult(search_value="CAT-001", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestNiIneterSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.ineter import NiIneterSource

        meta = NiIneterSource().meta()
        assert meta.name == "ni.ineter"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.ni.ineter import NiIneterSource

        src = NiIneterSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
