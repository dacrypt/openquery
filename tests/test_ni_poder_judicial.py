"""Tests for ni.poder_judicial — Nicaragua NICARAO court cases."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiPoderJudicialResult:
    def test_defaults(self):
        from openquery.models.ni.poder_judicial import NiPoderJudicialResult

        r = NiPoderJudicialResult()
        assert r.search_term == ""
        assert r.case_number == ""
        assert r.court == ""
        assert r.status == ""
        assert r.region == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ni.poder_judicial import NiPoderJudicialResult

        r = NiPoderJudicialResult(
            search_term="0123-2024-00001",
            case_number="0123-2024-00001",
            court="Juzgado Civil de Managua",
            status="En trámite",
            region="Managua",
        )
        dumped = r.model_dump_json()
        restored = NiPoderJudicialResult.model_validate_json(dumped)
        assert restored.search_term == "0123-2024-00001"
        assert restored.case_number == "0123-2024-00001"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.poder_judicial import NiPoderJudicialResult

        r = NiPoderJudicialResult(search_term="0123-2024-00001", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiPoderJudicialSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.poder_judicial import NiPoderJudicialSource

        meta = NiPoderJudicialSource().meta()
        assert meta.name == "ni.poder_judicial"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.ni.poder_judicial import NiPoderJudicialSource

        src = NiPoderJudicialSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_case_number_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"case_number": "0123-2024-00001"},
        )
        assert inp.extra.get("case_number") == "0123-2024-00001"

    def test_party_name_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"party_name": "JUAN GARCIA LOPEZ"},
        )
        assert inp.extra.get("party_name") == "JUAN GARCIA LOPEZ"


class TestNiPoderJudicialParseResult:
    def _parse(self, body_text: str, search_term: str = "0123-2024-00001"):
        from openquery.sources.ni.poder_judicial import NiPoderJudicialSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiPoderJudicialSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.case_number == ""
        assert result.court == ""
        assert result.status == ""
        assert result.region == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="0123-2024-00001")
        assert result.search_term == "0123-2024-00001"

    def test_case_number_parsed(self):
        result = self._parse("Expediente: 0123-2024-00001\nEstado: En trámite")
        assert result.case_number == "0123-2024-00001"

    def test_court_parsed(self):
        result = self._parse("Juzgado: Juzgado Civil de Managua\nEstado: En trámite")
        assert result.court == "Juzgado Civil de Managua"

    def test_status_parsed(self):
        result = self._parse("Estado: En trámite\nExpediente: 0123-2024-00001")
        assert result.status == "En trámite"

    def test_region_parsed(self):
        result = self._parse("Circunscripción: Managua\nExpediente: 0123-2024-00001")
        assert result.region == "Managua"

    def test_details_populated(self):
        result = self._parse("Expediente: 0123-2024-00001\nEstado: En trámite")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.ni.poder_judicial import NiPoderJudicialResult

        r = NiPoderJudicialResult(
            search_term="0123-2024-00001",
            case_number="0123-2024-00001",
            court="Juzgado Civil de Managua",
            status="En trámite",
            region="Managua",
        )
        data = r.model_dump_json()
        r2 = NiPoderJudicialResult.model_validate_json(data)
        assert r2.case_number == "0123-2024-00001"
        assert r2.court == "Juzgado Civil de Managua"
