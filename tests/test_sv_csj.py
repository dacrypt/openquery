"""Tests for sv.csj — El Salvador CSJ court cases source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSvCsjParseResult:
    def _parse(self, body_text: str, case_number: str = "1-MC-2023"):
        from openquery.sources.sv.csj import SvCsjSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SvCsjSource()
        return src._parse_result(page, case_number)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.court == ""
        assert result.status == ""
        assert result.parties == []

    def test_case_number_preserved(self):
        result = self._parse("", case_number="1-MC-2023")
        assert result.case_number == "1-MC-2023"

    def test_court_parsed_tribunal(self):
        result = self._parse("Tribunal: Juzgado Primero Civil\nEstado: En trámite")
        assert result.court == "Juzgado Primero Civil"

    def test_court_parsed_sala(self):
        result = self._parse("Sala: Sala de lo Civil\nEstado: Resuelto")
        assert result.court == "Sala de lo Civil"

    def test_status_parsed(self):
        result = self._parse("Estado: En trámite\nTribunal: Juzgado Primero")
        assert result.status == "En trámite"

    def test_parties_parsed(self):
        result = self._parse("Demandante: JUAN GARCIA\nDemandado: EMPRESA SA\nTribunal: Juzgado")
        assert len(result.parties) >= 1

    def test_details_populated(self):
        result = self._parse("Tribunal: Juzgado\nFecha: 2023-01-15")
        assert isinstance(result.details, dict)

    def test_model_roundtrip(self):
        from openquery.models.sv.csj import SvCsjResult

        r = SvCsjResult(
            case_number="1-MC-2023",
            court="Juzgado Primero Civil",
            status="En trámite",
            parties=["JUAN GARCIA", "EMPRESA SA"],
        )
        data = r.model_dump_json()
        r2 = SvCsjResult.model_validate_json(data)
        assert r2.case_number == "1-MC-2023"
        assert r2.court == "Juzgado Primero Civil"
        assert len(r2.parties) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.sv.csj import SvCsjResult

        r = SvCsjResult(case_number="1-MC-2023", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSvCsjSourceMeta:
    def test_meta(self):
        from openquery.sources.sv.csj import SvCsjSource

        meta = SvCsjSource().meta()
        assert meta.name == "sv.csj"
        assert meta.country == "SV"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_case_number_raises(self):
        from openquery.sources.sv.csj import SvCsjSource

        src = SvCsjSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_case_number_from_extra(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"case_number": "1-MC-2023"},
        )
        assert inp.extra.get("case_number") == "1-MC-2023"

    def test_case_number_from_document_number(self):
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="1-MC-2023",
        )
        assert inp.document_number == "1-MC-2023"
