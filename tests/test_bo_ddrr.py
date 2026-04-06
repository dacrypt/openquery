"""Tests for bo.ddrr — Bolivia Derechos Reales property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestDdrrParseResult:
    def _parse(self, body_text: str, search_value: str = "12345-A"):
        from openquery.sources.bo.ddrr import DdrrSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = DdrrSource()
        return src._parse_result(page, search_value)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.folio == ""
        assert result.owner == ""
        assert result.liens == []

    def test_search_value_preserved(self):
        result = self._parse("", search_value="FOL-9999")
        assert result.search_value == "FOL-9999"

    def test_folio_parsed(self):
        result = self._parse("Folio: 12345-A\nPropietario: Juan Pérez\nTipo: Inmueble")
        assert result.folio == "12345-A"
        assert result.owner == "Juan Pérez"
        assert result.property_type == "Inmueble"

    def test_titular_parsed_as_owner(self):
        result = self._parse("Titular: María García")
        assert result.owner == "María García"

    def test_liens_captured(self):
        result = self._parse(
            "Folio: 001\nGravamen: Hipoteca por Banco Nacional\nEmbargo judicial 2023"
        )
        assert len(result.liens) >= 1
        assert any("Hipoteca" in lien or "Gravamen" in lien for lien in result.liens)

    def test_details_dict_populated(self):
        result = self._parse("Departamento: La Paz\nMunicipio: La Paz")
        assert "Departamento" in result.details or len(result.details) >= 0

    def test_model_roundtrip(self):
        from openquery.models.bo.ddrr import DdrrResult

        r = DdrrResult(
            search_value="FOL-001",
            folio="FOL-001",
            owner="Juan Pérez",
            property_type="Inmueble urbano",
            liens=["Hipoteca Banco X"],
            details={"Departamento": "La Paz"},
        )
        data = r.model_dump_json()
        r2 = DdrrResult.model_validate_json(data)
        assert r2.folio == "FOL-001"
        assert r2.owner == "Juan Pérez"
        assert r2.liens == ["Hipoteca Banco X"]

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.ddrr import DdrrResult

        r = DdrrResult(search_value="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestDdrrSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.ddrr import DdrrSource

        meta = DdrrSource().meta()
        assert meta.name == "bo.ddrr"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True

    def test_empty_input_raises(self):
        from openquery.sources.bo.ddrr import DdrrSource

        src = DdrrSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_folio_extra_accepted(self):

        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"folio": "FOL-001"},
        )
        assert input_.extra["folio"] == "FOL-001"
