"""Tests for bo.segip — Bolivia SEGIP identity service source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSegipParseResult:
    def _parse(self, body_text: str, ci: str = "1234567"):
        from openquery.sources.bo.segip import SegipSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SegipSource()
        return src._parse_result(page, ci)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.nombre == ""
        assert result.document_status == ""

    def test_ci_preserved(self):
        result = self._parse("", ci="7654321")
        assert result.ci == "7654321"

    def test_parses_nombre(self):
        body = "Nombre: Juan Pérez López\nEstado: Vigente"
        result = self._parse(body)
        assert result.nombre == "Juan Pérez López"

    def test_parses_document_status(self):
        body = "Estado: Vigente\nNombre: María García"
        result = self._parse(body)
        assert result.document_status == "Vigente"

    def test_parses_vigencia_label(self):
        body = "Vigencia: Válido hasta 2027\nNombre: Carlos López"
        result = self._parse(body)
        assert result.document_status == "Válido hasta 2027"

    def test_model_roundtrip(self):
        from openquery.models.bo.segip import SegipResult

        r = SegipResult(
            ci="1234567",
            nombre="Juan Pérez",
            document_status="Vigente",
        )
        data = r.model_dump_json()
        r2 = SegipResult.model_validate_json(data)
        assert r2.ci == "1234567"
        assert r2.nombre == "Juan Pérez"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.segip import SegipResult

        r = SegipResult(ci="1234567", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSegipSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.segip import SegipSource

        meta = SegipSource().meta()
        assert meta.name == "bo.segip"
        assert meta.country == "BO"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_ci_raises(self):
        from openquery.sources.bo.segip import SegipSource

        src = SegipSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_document_number_used_as_ci(self):
        input_ = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="1234567",
        )
        assert input_.document_number == "1234567"
