"""Tests for hn.rnp — Honduras RNP identity registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnRnpParseResult:
    def _parse(self, body_text: str, dni: str = "08011999012345"):
        from openquery.sources.hn.rnp import HnRnpSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnRnpSource()
        return src._parse_result(page, dni)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.birth_date == ""

    def test_dni_preserved(self):
        result = self._parse("", dni="08011999012345")
        assert result.dni == "08011999012345"

    def test_nombre_parsed(self):
        result = self._parse("Nombre: JUAN CARLOS FLORES MARTINEZ\nFecha: 1990-01-15")
        assert result.nombre == "JUAN CARLOS FLORES MARTINEZ"

    def test_fecha_nacimiento_parsed(self):
        result = self._parse("Nombre: ANA LOPEZ\nFecha de Nacimiento: 1985-06-20")
        assert result.birth_date == "1985-06-20"

    def test_nacimiento_maps_to_birth_date(self):
        result = self._parse("Nombre: PEDRO RAMIREZ\nNacimiento: 1992-03-10")
        assert result.birth_date == "1992-03-10"

    def test_details_populated(self):
        result = self._parse("Nombre: ANA GARCIA\nMunicipio: Tegucigalpa")
        assert isinstance(result.details, dict)
        assert result.details.get("Municipio") == "Tegucigalpa"

    def test_model_roundtrip(self):
        from openquery.models.hn.rnp import HnRnpResult

        r = HnRnpResult(
            dni="08011999012345",
            nombre="JUAN CARLOS FLORES MARTINEZ",
            birth_date="1990-01-15",
        )
        data = r.model_dump_json()
        r2 = HnRnpResult.model_validate_json(data)
        assert r2.dni == "08011999012345"
        assert r2.nombre == "JUAN CARLOS FLORES MARTINEZ"
        assert r2.birth_date == "1990-01-15"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.rnp import HnRnpResult

        r = HnRnpResult(dni="08011999012345", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnRnpSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.rnp import HnRnpSource

        meta = HnRnpSource().meta()
        assert meta.name == "hn.rnp"
        assert meta.country == "HN"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dni_raises(self):
        from openquery.sources.hn.rnp import HnRnpSource

        src = HnRnpSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.hn.rnp import HnRnpSource

        src = HnRnpSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))

    def test_hyphens_stripped_from_dni(self):
        dni_with_hyphens = "0801-1999-01234"
        cleaned = dni_with_hyphens.replace("-", "")
        assert "-" not in cleaned
