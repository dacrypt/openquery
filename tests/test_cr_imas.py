"""Tests for cr.imas — Costa Rica IMAS social programs source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestImasParseResult:
    def _parse(self, body_text: str, cedula: str = "100000000"):
        from openquery.sources.cr.imas import ImasSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = ImasSource()
        return src._parse_result(page, cedula)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.beneficiary_name == ""
        assert result.program_name == ""
        assert result.beneficiary_status == ""

    def test_cedula_preserved(self):
        result = self._parse("", cedula="100000001")
        assert result.cedula == "100000001"

    def test_parses_beneficiary_name(self):
        body = "Nombre: Juan Perez\nPrograma: AVANCEMOS\nEstado: Activo"
        result = self._parse(body)
        assert result.beneficiary_name == "Juan Perez"

    def test_parses_program_name(self):
        body = "Programa: AVANCEMOS\nEstado: Activo"
        result = self._parse(body)
        assert result.program_name == "AVANCEMOS"

    def test_parses_status(self):
        body = "Estado: Inactivo"
        result = self._parse(body)
        assert result.beneficiary_status == "Inactivo"

    def test_model_roundtrip(self):
        from openquery.models.cr.imas import ImasResult

        r = ImasResult(cedula="100000000", program_name="AVANCEMOS", beneficiary_status="Activo")
        data = r.model_dump_json()
        r2 = ImasResult.model_validate_json(data)
        assert r2.program_name == "AVANCEMOS"

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.imas import ImasResult

        r = ImasResult(cedula="100000000", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestImasSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.imas import ImasSource

        meta = ImasSource().meta()
        assert meta.name == "cr.imas"
        assert meta.country == "CR"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_cedula_raises(self):
        from openquery.sources.cr.imas import ImasSource

        src = ImasSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))
