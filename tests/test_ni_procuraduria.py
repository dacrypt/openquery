"""Tests for ni.procuraduria — Nicaragua Procuraduría anticorruption source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiProcuraduriaParseResult:
    def _parse(self, body_text: str, search_term: str = "funcionario test"):
        from openquery.sources.ni.procuraduria import NiProcuraduriaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = NiProcuraduriaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.found is False
        assert result.record_type == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Juan NI")
        assert result.search_term == "Juan NI"

    def test_found_on_keyword(self):
        result = self._parse("Expediente: NI-2024-001\nRegistro encontrado")
        assert result.found is True

    def test_parses_status(self):
        body = "Estado: Investigado\nTipo: Anticorrupción"
        result = self._parse(body)
        assert result.status == "Investigado"

    def test_model_roundtrip(self):
        from openquery.models.ni.procuraduria import NiProcuraduriaResult

        r = NiProcuraduriaResult(search_term="test", found=True, status="Investigado")
        data = r.model_dump_json()
        r2 = NiProcuraduriaResult.model_validate_json(data)
        assert r2.found is True

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.procuraduria import NiProcuraduriaResult

        r = NiProcuraduriaResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestNiProcuraduriaSourceMeta:
    def test_meta(self):
        from openquery.sources.ni.procuraduria import NiProcuraduriaSource

        meta = NiProcuraduriaSource().meta()
        assert meta.name == "ni.procuraduria"
        assert meta.country == "NI"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.ni.procuraduria import NiProcuraduriaSource

        src = NiProcuraduriaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
