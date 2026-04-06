"""Tests for cr.tse — Costa Rica TSE electoral registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.cr.tse import CrTseResult
from openquery.sources.base import DocumentType, QueryInput


class TestCrTseResult:
    """Model default values, JSON roundtrip, audit exclusion."""

    def test_defaults(self):
        r = CrTseResult()
        assert r.cedula == ""
        assert r.nombre == ""
        assert r.genero == ""
        assert r.distrito == ""
        assert r.fecha_vencimiento == ""
        assert r.precinto == ""
        assert r.details == ""
        assert r.audit is None

    def test_queried_at_default(self):
        r = CrTseResult()
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        r = CrTseResult(cedula="123456789", nombre="JUAN PEREZ GOMEZ", genero="MASCULINO")
        restored = CrTseResult.model_validate_json(r.model_dump_json())
        assert restored.cedula == "123456789"
        assert restored.nombre == "JUAN PEREZ GOMEZ"
        assert restored.genero == "MASCULINO"

    def test_audit_excluded_from_json(self):
        r = CrTseResult(cedula="123", audit=b"pdf-data")
        dumped = r.model_dump_json()
        assert "audit" not in dumped

    def test_audit_excluded_from_dict(self):
        r = CrTseResult(cedula="123", audit={"key": "val"})
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestCrTseSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.tse import CrTseSource
        meta = CrTseSource().meta()
        assert meta.name == "cr.tse"
        assert meta.country == "CR"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10

    def test_missing_cedula_raises(self):
        from openquery.sources.cr.tse import CrTseSource
        src = CrTseSource()
        with pytest.raises(SourceError, match="Cédula is required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))


class TestCrTseParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, cedula: str = "123456789") -> CrTseResult:
        from openquery.sources.cr.tse import CrTseSource
        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CrTseSource()
        return src._parse_result(page, cedula)

    def test_cedula_preserved(self):
        result = self._parse("Sin resultados", cedula="987654321")
        assert result.cedula == "987654321"

    def test_parses_nombre(self):
        body = "Nombre: JUAN CARLOS PEREZ GOMEZ\nGénero: MASCULINO\n"
        result = self._parse(body)
        assert result.nombre == "JUAN CARLOS PEREZ GOMEZ"

    def test_parses_genero(self):
        body = "Género: FEMENINO\nDistrito: SAN JOSE\n"
        result = self._parse(body)
        assert result.genero == "FEMENINO"

    def test_parses_genero_alt_label(self):
        body = "Genero: MASCULINO\n"
        result = self._parse(body)
        assert result.genero == "MASCULINO"

    def test_parses_sexo_label(self):
        body = "Sexo: M\n"
        result = self._parse(body)
        assert result.genero == "M"

    def test_parses_distrito(self):
        body = "Distrito: ESCAZU\n"
        result = self._parse(body)
        assert result.distrito == "ESCAZU"

    def test_parses_fecha_vencimiento(self):
        body = "Fecha de Vencimiento: 31/12/2027\n"
        result = self._parse(body)
        assert result.fecha_vencimiento == "31/12/2027"

    def test_parses_vencimiento_short(self):
        body = "Vencimiento: 2028-06-30\n"
        result = self._parse(body)
        assert result.fecha_vencimiento == "2028-06-30"

    def test_parses_precinto(self):
        body = "Precinto: 001\n"
        result = self._parse(body)
        assert result.precinto == "001"

    def test_details_truncated_to_500(self):
        body = "X" * 1000
        result = self._parse(body)
        assert len(result.details) == 500

    def test_empty_body(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.genero == ""

    def test_line_without_colon_ignored(self):
        body = "Nombre sin dos puntos\nNombre: VALIDO\n"
        result = self._parse(body)
        assert result.nombre == "VALIDO"
