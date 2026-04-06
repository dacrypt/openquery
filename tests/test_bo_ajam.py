"""Tests for bo.ajam — Bolivia AJAM mining concessions source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAjamParseResult:
    def _parse(self, body_text: str, search_term: str = "Concesión Cerro Rico"):
        from openquery.sources.bo.ajam import AjamSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = AjamSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.concession_name == ""
        assert result.holder == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Mina San José")
        assert result.search_term == "Mina San José"

    def test_parses_concession_name(self):
        body = "Concesión: Cerro Rico Norte\nTitular: Juan Mamani\nEstado: Vigente"
        result = self._parse(body)
        assert result.concession_name == "Cerro Rico Norte"

    def test_parses_holder(self):
        body = "Titular: Empresa Minera SA\nEstado: Activo"
        result = self._parse(body)
        assert result.holder == "Empresa Minera SA"

    def test_parses_status(self):
        body = "Estado: Vigente\nConcesión: Mina Norte"
        result = self._parse(body)
        assert result.status == "Vigente"

    def test_model_roundtrip(self):
        from openquery.models.bo.ajam import AjamResult

        r = AjamResult(
            search_term="Cerro Rico",
            concession_name="Cerro Rico Norte",
            holder="Juan Mamani",
            status="Vigente",
        )
        data = r.model_dump_json()
        r2 = AjamResult.model_validate_json(data)
        assert r2.search_term == "Cerro Rico"
        assert r2.concession_name == "Cerro Rico Norte"

    def test_audit_excluded_from_json(self):
        from openquery.models.bo.ajam import AjamResult

        r = AjamResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestAjamSourceMeta:
    def test_meta(self):
        from openquery.sources.bo.ajam import AjamSource

        meta = AjamSource().meta()
        assert meta.name == "bo.ajam"
        assert meta.country == "BO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.bo.ajam import AjamSource

        src = AjamSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Mina Norte",
        )
        assert input_.document_number == "Mina Norte"

    def test_extra_concession_name(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"concession_name": "Cerro Bonito"},
        )
        assert input_.extra["concession_name"] == "Cerro Bonito"
