"""Tests for hn.poder_judicial — Honduras SEJE court cases source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnPoderJudicialParseResult:
    def _parse(self, body_text: str, case_number: str = "0801-2023-00123"):
        from openquery.sources.hn.poder_judicial import HnPoderJudicialSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = HnPoderJudicialSource()
        return src._parse_result(page, case_number)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.case_number == "0801-2023-00123"
        assert result.court == ""
        assert result.status == ""
        assert result.proceedings == ""

    def test_case_number_preserved(self):
        result = self._parse("", case_number="0801-2023-00123")
        assert result.case_number == "0801-2023-00123"

    def test_juzgado_parsed(self):
        result = self._parse("Juzgado: Juzgado de Letras Civil\nEstado: Activo")
        assert result.court == "Juzgado de Letras Civil"

    def test_tribunal_maps_to_court(self):
        result = self._parse("Tribunal: Corte de Apelaciones\nEstado: Resuelto")
        assert result.court == "Corte de Apelaciones"

    def test_sala_maps_to_court(self):
        result = self._parse("Sala: Sala Constitucional\nEstado: En trámite")
        assert result.court == "Sala Constitucional"

    def test_estado_parsed(self):
        result = self._parse("Juzgado: Juzgado de Letras\nEstado: Archivado")
        assert result.status == "Archivado"

    def test_actuacion_parsed(self):
        result = self._parse("Juzgado: Juzgado Civil\nActuación: Sentencia pronunciada")
        assert result.proceedings == "Sentencia pronunciada"

    def test_diligencia_maps_to_proceedings(self):
        result = self._parse("Juzgado: Juzgado Civil\nDiligencia: Notificación enviada")
        assert result.proceedings == "Notificación enviada"

    def test_details_populated(self):
        result = self._parse("Juzgado: Juzgado Civil\nFecha: 2023-03-15")
        assert isinstance(result.details, dict)
        assert result.details.get("Fecha") == "2023-03-15"

    def test_model_roundtrip(self):
        from openquery.models.hn.poder_judicial import HnPoderJudicialResult

        r = HnPoderJudicialResult(
            case_number="0801-2023-00123",
            court="Juzgado de Letras Civil",
            status="En trámite",
            proceedings="Audiencia programada",
        )
        data = r.model_dump_json()
        r2 = HnPoderJudicialResult.model_validate_json(data)
        assert r2.case_number == "0801-2023-00123"
        assert r2.court == "Juzgado de Letras Civil"
        assert r2.status == "En trámite"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.poder_judicial import HnPoderJudicialResult

        r = HnPoderJudicialResult(case_number="0801-2023-00123", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnPoderJudicialSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.poder_judicial import HnPoderJudicialSource

        meta = HnPoderJudicialSource().meta()
        assert meta.name == "hn.poder_judicial"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_case_number_raises(self):
        from openquery.sources.hn.poder_judicial import HnPoderJudicialSource

        src = HnPoderJudicialSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_case_number(self):
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="0801-2023-00123")
        assert qi.document_number == "0801-2023-00123"
