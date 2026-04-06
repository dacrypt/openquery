"""Tests for ve.banavih — Venezuela BANAVIH FAOV housing savings source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestBanavihParseResult:
    def _parse(self, body_text: str, cedula: str = "12345678"):
        from openquery.sources.ve.banavih import BanavihSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = BanavihSource()
        return src._parse_result(page, cedula)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.contribution_status == ""
        assert result.employer == ""

    def test_cedula_preserved(self):
        result = self._parse("", cedula="87654321")
        assert result.cedula == "87654321"

    def test_parses_contribution_status(self):
        body = "Estado: Al día\nEmpleador: Empresa XYZ"
        result = self._parse(body)
        assert result.contribution_status == "Al día"

    def test_parses_employer(self):
        body = "Patrono: Empresa ABC C.A.\nEstado: Activo"
        result = self._parse(body)
        assert result.employer == "Empresa ABC C.A."

    def test_parses_empleador_label(self):
        body = "Empleador: Corporación Nacional\nEstado: Activo"
        result = self._parse(body)
        assert result.employer == "Corporación Nacional"

    def test_model_roundtrip(self):
        from openquery.models.ve.banavih import BanavihResult

        r = BanavihResult(
            cedula="12345678",
            contribution_status="Al día",
            employer="Empresa XYZ",
        )
        data = r.model_dump_json()
        r2 = BanavihResult.model_validate_json(data)
        assert r2.cedula == "12345678"
        assert r2.contribution_status == "Al día"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.banavih import BanavihResult

        r = BanavihResult(cedula="12345678", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestBanavihSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.banavih import BanavihSource

        meta = BanavihSource().meta()
        assert meta.name == "ve.banavih"
        assert meta.country == "VE"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_cedula_raises(self):
        from openquery.sources.ve.banavih import BanavihSource

        src = BanavihSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))

    def test_document_number_used_as_cedula(self):
        input_ = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="12345678",
        )
        assert input_.document_number == "12345678"
