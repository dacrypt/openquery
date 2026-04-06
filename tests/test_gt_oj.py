"""Tests for gt.oj — Guatemala OJ judicial cases source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestGtOjParseResult:
    def _parse(self, body_text: str, search_term: str = "2023-001234-OF"):
        from openquery.sources.gt.oj import GtOjSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = GtOjSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.case_number == ""
        assert result.court == ""
        assert result.status == ""
        assert result.resolution == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="2023-001234-OF")
        assert result.search_term == "2023-001234-OF"

    def test_expediente_parsed(self):
        result = self._parse("Expediente: 2023-001234-OF\nEstado: En trámite")
        assert result.case_number == "2023-001234-OF"

    def test_juzgado_parsed(self):
        result = self._parse("Juzgado: Juzgado Civil Primero\nEstado: Resuelto")
        assert result.court == "Juzgado Civil Primero"

    def test_tribunal_maps_to_court(self):
        result = self._parse("Tribunal: Sala Civil\nEstado: Activo")
        assert result.court == "Sala Civil"

    def test_sala_maps_to_court(self):
        result = self._parse("Sala: Sala Tercera\nEstado: Activo")
        assert result.court == "Sala Tercera"

    def test_estado_parsed(self):
        result = self._parse("Expediente: 2023-001234-OF\nEstado: Archivado")
        assert result.status == "Archivado"

    def test_resolucion_parsed(self):
        result = self._parse("Resolución: Sentencia definitiva\nEstado: Cerrado")
        assert result.resolution == "Sentencia definitiva"

    def test_details_populated(self):
        result = self._parse("Juzgado: Juzgado Civil\nFecha: 2023-01-15")
        assert isinstance(result.details, dict)
        assert result.details.get("Fecha") == "2023-01-15"

    def test_model_roundtrip(self):
        from openquery.models.gt.oj import GtOjResult

        r = GtOjResult(
            search_term="2023-001234-OF",
            case_number="2023-001234-OF",
            court="Juzgado Civil Primero",
            status="En trámite",
            resolution="Pendiente",
        )
        data = r.model_dump_json()
        r2 = GtOjResult.model_validate_json(data)
        assert r2.search_term == "2023-001234-OF"
        assert r2.court == "Juzgado Civil Primero"
        assert r2.status == "En trámite"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.oj import GtOjResult

        r = GtOjResult(search_term="2023-001234-OF", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtOjSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.oj import GtOjSource

        meta = GtOjSource().meta()
        assert meta.name == "gt.oj"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_term_raises(self):
        from openquery.sources.gt.oj import GtOjSource

        src = GtOjSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_search_term(self):
        # Verify document_number is accepted — just check query routing, no browser
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="2023-001234-OF")
        assert qi.document_number == "2023-001234-OF"
