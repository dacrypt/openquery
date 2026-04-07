"""Tests for hn.registro_propiedad — Honduras property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnRegistroPropiedadParseResult:
    def _parse(self, body_text: str, property_number: str = "HN-2024-001"):
        from openquery.sources.hn.registro_propiedad import HnRegistroPropiedadSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnRegistroPropiedadSource()
        return src._parse_result(page, property_number)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.owner_name == ""
        assert result.property_type == ""

    def test_property_number_preserved(self):
        result = self._parse("", property_number="HN-999")
        assert result.property_number == "HN-999"

    def test_parses_owner(self):
        body = "Propietario: Juan Honduras\nTipo: Urbano"
        result = self._parse(body)
        assert result.owner_name == "Juan Honduras"

    def test_parses_location(self):
        body = "Ubicación: Tegucigalpa, MDC\nEstado: Activo"
        result = self._parse(body)
        assert result.location == "Tegucigalpa, MDC"

    def test_model_roundtrip(self):
        from openquery.models.hn.registro_propiedad import HnRegistroPropiedadResult

        r = HnRegistroPropiedadResult(property_number="HN-001", owner_name="Juan HN", location="Tegucigalpa")  # noqa: E501
        data = r.model_dump_json()
        r2 = HnRegistroPropiedadResult.model_validate_json(data)
        assert r2.property_number == "HN-001"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.registro_propiedad import HnRegistroPropiedadResult

        r = HnRegistroPropiedadResult(property_number="HN-001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnRegistroPropiedadSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.registro_propiedad import HnRegistroPropiedadSource

        meta = HnRegistroPropiedadSource().meta()
        assert meta.name == "hn.registro_propiedad"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_property_raises(self):
        from openquery.sources.hn.registro_propiedad import HnRegistroPropiedadSource

        src = HnRegistroPropiedadSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
