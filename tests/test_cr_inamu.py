"""Tests for cr.inamu — Costa Rica INAMU women's rights registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestInamuParseResult:
    def _parse(self, body_text: str, search_term: str = "test"):
        from openquery.sources.cr.inamu import InamuSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = InamuSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.found is False
        assert result.registry_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Centro INAMU")
        assert result.search_term == "Centro INAMU"

    def test_found_on_keyword(self):
        result = self._parse("Registro: encontrado\nNombre: Test")
        assert result.found is True

    def test_parses_status(self):
        body = "Estado: Activo\nTipo: Registro"
        result = self._parse(body)
        assert result.status == "Activo"

    def test_model_roundtrip(self):
        from openquery.models.cr.inamu import InamuResult

        r = InamuResult(search_term="test", found=True, status="Activo")
        data = r.model_dump_json()
        r2 = InamuResult.model_validate_json(data)
        assert r2.search_term == "test"
        assert r2.found is True

    def test_audit_excluded_from_json(self):
        from openquery.models.cr.inamu import InamuResult

        r = InamuResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestInamuSourceMeta:
    def test_meta(self):
        from openquery.sources.cr.inamu import InamuSource

        meta = InamuSource().meta()
        assert meta.name == "cr.inamu"
        assert meta.country == "CR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.cr.inamu import InamuSource

        src = InamuSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_fallback(self):
        input_ = QueryInput(document_type=DocumentType.CUSTOM, document_number="INAMU Centro")
        assert input_.document_number == "INAMU Centro"
