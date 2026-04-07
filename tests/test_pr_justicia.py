"""Tests for pr.justicia — Puerto Rico Department of Justice registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPrJusticiaParseResult:
    def _parse(self, body_text: str, search_term: str = "Entidad Test"):
        from openquery.sources.pr.justicia import PrJusticiaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = PrJusticiaSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.entity_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="ONG PR")
        assert result.search_term == "ONG PR"

    def test_parses_entity_name(self):
        body = "Entidad: ONG Solidaria PR\nEstado: Activa"
        result = self._parse(body)
        assert result.entity_name == "ONG Solidaria PR"

    def test_parses_status(self):
        body = "Estado: Registrada\nTipo: Fundación"
        result = self._parse(body)
        assert result.status == "Registrada"

    def test_model_roundtrip(self):
        from openquery.models.pr.justicia import PrJusticiaResult

        r = PrJusticiaResult(search_term="test", entity_name="ONG PR", status="Active")
        data = r.model_dump_json()
        r2 = PrJusticiaResult.model_validate_json(data)
        assert r2.entity_name == "ONG PR"

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.justicia import PrJusticiaResult

        r = PrJusticiaResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestPrJusticiaSourceMeta:
    def test_meta(self):
        from openquery.sources.pr.justicia import PrJusticiaSource

        meta = PrJusticiaSource().meta()
        assert meta.name == "pr.justicia"
        assert meta.country == "PR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.pr.justicia import PrJusticiaSource

        src = PrJusticiaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
