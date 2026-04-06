"""Tests for gt.tse — Guatemala TSE electoral registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtTseParseResult:
    def _parse(self, body_text: str, dpi: str = "1234567890101"):
        from openquery.sources.gt.tse import GtTseSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = GtTseSource()
        return src._parse_result(page, dpi)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.estado_electoral == ""
        assert result.lugar_votacion == ""
        assert result.municipio == ""
        assert result.afiliacion == ""

    def test_dpi_preserved(self):
        result = self._parse("", dpi="1234567890101")
        assert result.dpi == "1234567890101"

    def test_nombre_parsed(self):
        result = self._parse("Nombre: MARIA JOSE GARCIA LOPEZ\nEstado: Activo")
        assert result.nombre == "MARIA JOSE GARCIA LOPEZ"

    def test_estado_electoral_parsed(self):
        result = self._parse("Estado: Empadronado\nNombre: PEDRO RAMIREZ")
        assert result.estado_electoral == "Empadronado"

    def test_lugar_votacion_parsed(self):
        result = self._parse("Lugar: Escuela Nacional Central\nMunicipio: Guatemala")
        assert result.lugar_votacion == "Escuela Nacional Central"

    def test_centro_votacion_parsed(self):
        result = self._parse("Centro: Instituto Nacional Mixto Nocturno\nMunicipio: Mixco")
        assert result.lugar_votacion == "Instituto Nacional Mixto Nocturno"

    def test_municipio_parsed(self):
        result = self._parse("Nombre: ANA MARTINEZ\nMunicipio: Villa Nueva")
        assert result.municipio == "Villa Nueva"

    def test_afiliacion_parsed(self):
        result = self._parse("Nombre: CARLOS LOPEZ\nAfiliacion: Partido Patriota")
        assert result.afiliacion == "Partido Patriota"

    def test_partido_maps_to_afiliacion(self):
        result = self._parse("Nombre: LUIS PEREZ\nPartido: UNE")
        assert result.afiliacion == "UNE"

    def test_details_populated(self):
        result = self._parse("Nombre: ANA MARTINEZ\nDepartamento: Guatemala")
        assert isinstance(result.details, dict)
        assert result.details.get("Departamento") == "Guatemala"

    def test_model_roundtrip(self):
        from openquery.models.gt.tse import GtTseResult

        r = GtTseResult(
            dpi="1234567890101",
            nombre="MARIA JOSE GARCIA",
            estado_electoral="Empadronado",
            lugar_votacion="Escuela Nacional",
            municipio="Guatemala",
            afiliacion="Ninguno",
        )
        data = r.model_dump_json()
        r2 = GtTseResult.model_validate_json(data)
        assert r2.dpi == "1234567890101"
        assert r2.nombre == "MARIA JOSE GARCIA"
        assert r2.municipio == "Guatemala"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.tse import GtTseResult

        r = GtTseResult(dpi="1234567890101", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtTseSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.tse import GtTseSource

        meta = GtTseSource().meta()
        assert meta.name == "gt.tse"
        assert meta.country == "GT"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_dpi_raises(self):
        from openquery.sources.gt.tse import GtTseSource

        src = GtTseSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_wrong_document_type_raises(self):
        from openquery.sources.gt.tse import GtTseSource

        src = GtTseSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
