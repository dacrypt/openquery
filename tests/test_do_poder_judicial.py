"""Tests for do.poder_judicial — Dominican Republic court cases source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestDoPodeJudicialParseResult:
    def _parse(self, body_text: str, search_term: str = "2023-0001-001"):
        from openquery.sources.do.poder_judicial import DoPodeJudicialSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = DoPodeJudicialSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.case_number == ""
        assert result.court == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="2024-0002-001")
        assert result.search_term == "2024-0002-001"

    def test_parses_case_number(self):
        body = "Expediente: 2023-0001-001\nTribunal: Juzgado Civil\nEstado: En proceso"
        result = self._parse(body)
        assert result.case_number == "2023-0001-001"

    def test_parses_court(self):
        body = "Tribunal: Cámara Civil Santo Domingo\nEstado: Cerrado"
        result = self._parse(body)
        assert result.court == "Cámara Civil Santo Domingo"

    def test_parses_status(self):
        body = "Estado: En proceso\nExpediente: 2023-0001"
        result = self._parse(body)
        assert result.status == "En proceso"

    def test_model_roundtrip(self):
        from openquery.models.do.poder_judicial import DoPodeJudicialResult

        r = DoPodeJudicialResult(
            search_term="2023-0001-001",
            case_number="2023-0001-001",
            court="Juzgado Civil",
            status="En proceso",
        )
        data = r.model_dump_json()
        r2 = DoPodeJudicialResult.model_validate_json(data)
        assert r2.search_term == "2023-0001-001"
        assert r2.case_number == "2023-0001-001"

    def test_audit_excluded_from_json(self):
        from openquery.models.do.poder_judicial import DoPodeJudicialResult

        r = DoPodeJudicialResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestDoPodeJudicialSourceMeta:
    def test_meta(self):
        from openquery.sources.do.poder_judicial import DoPodeJudicialSource

        meta = DoPodeJudicialSource().meta()
        assert meta.name == "do.poder_judicial"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.do.poder_judicial import DoPodeJudicialSource

        src = DoPodeJudicialSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="2023-0001-001",
        )
        assert input_.document_number == "2023-0001-001"
