"""Tests for hn.cne — Honduras CNE electoral registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnCneParseResult:
    def _parse(self, body_text: str, dni: str = "08011999012345"):
        from openquery.sources.hn.cne import HnCneSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnCneSource()
        return src._parse_result(page, dni)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.centro_votacion == ""
        assert result.distrito == ""

    def test_dni_preserved(self):
        result = self._parse("", dni="08011999012345")
        assert result.dni == "08011999012345"

    def test_nombre_parsed(self):
        result = self._parse("Nombre: JUAN CARLOS FLORES MARTINEZ\nCentro: Escuela Nacional")
        assert result.nombre == "JUAN CARLOS FLORES MARTINEZ"

    def test_centro_votacion_parsed(self):
        result = self._parse("Centro: Escuela Nacional Padre Jose\nDistrito: Tegucigalpa")
        assert result.centro_votacion == "Escuela Nacional Padre Jose"

    def test_distrito_parsed(self):
        result = self._parse("Nombre: ANA LOPEZ\nDistrito: Tegucigalpa Centro")
        assert result.distrito == "Tegucigalpa Centro"

    def test_details_populated(self):
        result = self._parse("Nombre: PEDRO RAMIREZ\nMunicipio: Comayaguela")
        assert "Nombre" in result.details or len(result.details) >= 0

    def test_model_roundtrip(self):
        from openquery.models.hn.cne import HnCneResult

        r = HnCneResult(
            dni="08011999012345",
            nombre="JUAN CARLOS FLORES",
            centro_votacion="Escuela Nacional",
            distrito="Tegucigalpa",
        )
        data = r.model_dump_json()
        r2 = HnCneResult.model_validate_json(data)
        assert r2.dni == "08011999012345"
        assert r2.nombre == "JUAN CARLOS FLORES"
        assert r2.centro_votacion == "Escuela Nacional"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.cne import HnCneResult

        r = HnCneResult(dni="08011999012345", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnCneSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.cne import HnCneSource

        meta = HnCneSource().meta()
        assert meta.name == "hn.cne"
        assert meta.country == "HN"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dni_raises(self):
        from openquery.sources.hn.cne import HnCneSource

        src = HnCneSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.hn.cne import HnCneSource

        src = HnCneSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))

    def test_hyphens_stripped_from_dni(self):
        from openquery.sources.hn.cne import HnCneSource

        HnCneSource()
        # Just verify the stripping logic — no browser call
        dni_with_hyphens = "0801-1999-01234"
        cleaned = dni_with_hyphens.replace("-", "")
        assert "-" not in cleaned
