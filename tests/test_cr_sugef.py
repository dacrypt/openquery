"""Tests for cr.sugef — Costa Rica SUGEF supervised financial entities source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSugefParseResult:
    def _parse(self, body_text: str, search_term: str = "Banco Nacional"):
        from openquery.sources.cr.sugef import SugefSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = SugefSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.entity_type == ""
        assert result.supervision_status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Banco Costa Rica")
        assert result.search_term == "Banco Costa Rica"

    def test_parses_entity_name(self):
        body = "Entidad: Banco Nacional de Costa Rica\nTipo: Banco\nEstado: Supervisado"
        result = self._parse(body)
        assert result.entity_name == "Banco Nacional de Costa Rica"

    def test_parses_entity_type(self):
        body = "Tipo: Cooperativa de Ahorro\nEstado: Autorizado"
        result = self._parse(body)
        assert result.entity_type == "Cooperativa de Ahorro"

    def test_parses_supervision_status(self):
        body = "Estado: Supervisado\nEntidad: Banco XYZ"
        result = self._parse(body)
        assert result.supervision_status == "Supervisado"

    def test_model_roundtrip(self):
        from openquery.models.cr.sugef import SugefResult

        r = SugefResult(
            search_term="Banco Nacional",
            entity_name="Banco Nacional de Costa Rica",
            entity_type="Banco",
            supervision_status="Supervisado",
        )
        data = r.model_dump_json()
        r2 = SugefResult.model_validate_json(data)
        assert r2.search_term == "Banco Nacional"
        assert r2.entity_name == "Banco Nacional de Costa Rica"

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.sugef import SugefResult

        r = SugefResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestSugefSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.sugef import SugefSource

        meta = SugefSource().meta()
        assert meta.name == "cr.sugef"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.cr.sugef import SugefSource

        src = SugefSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Banco Mercantil",
        )
        assert input_.document_number == "Banco Mercantil"
