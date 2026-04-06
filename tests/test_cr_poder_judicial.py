"""Tests for cr.poder_judicial — Costa Rica Poder Judicial court case lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.cr.poder_judicial import CrPoderJudicialResult
from openquery.sources.base import DocumentType, QueryInput


class TestCrPoderJudicialResult:
    """Model default values, JSON roundtrip, audit exclusion."""

    def test_defaults(self):
        r = CrPoderJudicialResult()
        assert r.search_value == ""
        assert r.case_number == ""
        assert r.court == ""
        assert r.status == ""
        assert r.parties == ""
        assert r.filing_date == ""
        assert r.details == ""
        assert r.audit is None

    def test_queried_at_default(self):
        r = CrPoderJudicialResult()
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        r = CrPoderJudicialResult(
            search_value="01-000100-0007-CI",
            case_number="01-000100-0007-CI",
            court="Juzgado Civil de Mayor Cuantía",
            status="Activo",
        )
        restored = CrPoderJudicialResult.model_validate_json(r.model_dump_json())
        assert restored.search_value == "01-000100-0007-CI"
        assert restored.case_number == "01-000100-0007-CI"
        assert restored.court == "Juzgado Civil de Mayor Cuantía"
        assert restored.status == "Activo"

    def test_audit_excluded_from_json(self):
        r = CrPoderJudicialResult(search_value="ABC", audit=b"pdf-data")
        dumped = r.model_dump_json()
        assert "audit" not in dumped

    def test_audit_excluded_from_dict(self):
        r = CrPoderJudicialResult(search_value="ABC", audit={"key": "val"})
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestCrPoderJudicialSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.poder_judicial import CrPoderJudicialSource
        meta = CrPoderJudicialSource().meta()
        assert meta.name == "cr.poder_judicial"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10

    def test_missing_search_value_raises(self):
        from openquery.sources.cr.poder_judicial import CrPoderJudicialSource
        src = CrPoderJudicialSource()
        with pytest.raises(SourceError, match="Case number or cedula is required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestCrPoderJudicialParseResult:
    """Test _parse_result with mocked page."""

    def _parse(
        self, body_text: str, search_value: str = "01-000100-0007-CI"
    ) -> CrPoderJudicialResult:
        from openquery.sources.cr.poder_judicial import CrPoderJudicialSource
        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CrPoderJudicialSource()
        return src._parse_result(page, search_value)

    def test_search_value_preserved(self):
        result = self._parse("Sin resultados", search_value="01-000100-0007-CI")
        assert result.search_value == "01-000100-0007-CI"

    def test_parses_expediente(self):
        body = "Expediente: 01-000100-0007-CI\n"
        result = self._parse(body)
        assert result.case_number == "01-000100-0007-CI"

    def test_parses_numero_expediente(self):
        body = "Número de Expediente: 01-000200-0007-CI\n"
        result = self._parse(body)
        assert result.case_number == "01-000200-0007-CI"

    def test_parses_despacho(self):
        body = "Despacho: Juzgado Civil de Mayor Cuantía\n"
        result = self._parse(body)
        assert result.court == "Juzgado Civil de Mayor Cuantía"

    def test_parses_juzgado(self):
        body = "Juzgado: Juzgado Penal de Hacienda\n"
        result = self._parse(body)
        assert result.court == "Juzgado Penal de Hacienda"

    def test_parses_tribunal(self):
        body = "Tribunal: Tribunal Contencioso Administrativo\n"
        result = self._parse(body)
        assert result.court == "Tribunal Contencioso Administrativo"

    def test_parses_estado(self):
        body = "Estado: Activo\n"
        result = self._parse(body)
        assert result.status == "Activo"

    def test_parses_etapa(self):
        body = "Etapa: Sentencia\n"
        result = self._parse(body)
        assert result.status == "Sentencia"

    def test_parses_partes(self):
        body = "Partes: Juan Pérez vs. Estado CR\n"
        result = self._parse(body)
        assert result.parties == "Juan Pérez vs. Estado CR"

    def test_parses_actor(self):
        body = "Actor: Empresa XYZ S.A.\n"
        result = self._parse(body)
        assert result.parties == "Empresa XYZ S.A."

    def test_parses_fecha_entrada(self):
        body = "Fecha de Entrada: 15/03/2022\n"
        result = self._parse(body)
        assert result.filing_date == "15/03/2022"

    def test_parses_ingreso(self):
        body = "Ingreso: 01/01/2021\n"
        result = self._parse(body)
        assert result.filing_date == "01/01/2021"

    def test_details_truncated_to_500(self):
        body = "X" * 1000
        result = self._parse(body)
        assert len(result.details) == 500

    def test_empty_body(self):
        result = self._parse("")
        assert result.case_number == ""
        assert result.status == ""

    def test_multiple_fields_parsed(self):
        body = (
            "Expediente: 01-000100-0007-CI\n"
            "Despacho: Juzgado Civil de Mayor Cuantía\n"
            "Estado: Activo\n"
            "Partes: Juan Pérez vs. Estado CR\n"
            "Fecha de Entrada: 15/03/2022\n"
        )
        result = self._parse(body)
        assert result.case_number == "01-000100-0007-CI"
        assert result.court == "Juzgado Civil de Mayor Cuantía"
        assert result.status == "Activo"
        assert result.parties == "Juan Pérez vs. Estado CR"
        assert result.filing_date == "15/03/2022"
