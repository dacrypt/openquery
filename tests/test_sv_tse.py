"""Tests for sv.tse — El Salvador TSE electoral registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvTseParseResult:
    def _parse(self, body_text: str, dui: str = "00000000-0"):
        from openquery.sources.sv.tse import SvTseSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SvTseSource()
        return src._parse_result(page, dui)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.centro_votacion == ""
        assert result.municipio == ""

    def test_dui_preserved(self):
        result = self._parse("", dui="00000000-0")
        assert result.dui == "00000000-0"

    def test_nombre_parsed(self):
        result = self._parse("Nombre: MARIA JOSE GARCIA LOPEZ\nCentro: Centro Escolar Nacional")
        assert result.nombre == "MARIA JOSE GARCIA LOPEZ"

    def test_centro_votacion_parsed(self):
        result = self._parse("Centro: Centro Escolar Ramon Alvarez\nMunicipio: San Salvador")
        assert result.centro_votacion == "Centro Escolar Ramon Alvarez"

    def test_municipio_parsed(self):
        result = self._parse("Nombre: CARLOS RIVAS\nMunicipio: Santa Ana")
        assert result.municipio == "Santa Ana"

    def test_details_populated(self):
        result = self._parse("Nombre: ANA MARTINEZ\nDepartamento: La Libertad")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.sv.tse import SvTseResult

        r = SvTseResult(
            dui="00000000-0",
            nombre="MARIA JOSE GARCIA",
            centro_votacion="Centro Escolar Nacional",
            municipio="San Salvador",
        )
        data = r.model_dump_json()
        r2 = SvTseResult.model_validate_json(data)
        assert r2.dui == "00000000-0"
        assert r2.nombre == "MARIA JOSE GARCIA"
        assert r2.municipio == "San Salvador"

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.tse import SvTseResult

        r = SvTseResult(dui="00000000-0", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvTseSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.tse import SvTseSource

        meta = SvTseSource().meta()
        assert meta.name == "sv.tse"
        assert meta.country == "SV"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dui_raises(self):
        from openquery.sources.sv.tse import SvTseSource

        src = SvTseSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.sv.tse import SvTseSource

        src = SvTseSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
