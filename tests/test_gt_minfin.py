"""Tests for gt.minfin — Guatemala MINFIN budget data source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestMinfinParseResult:
    def _parse(self, body_text: str, search_term: str = "Ministerio Educacion"):
        from openquery.sources.gt.minfin import MinfinSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = MinfinSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.budget_amount == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="MINEDUC")
        assert result.search_term == "MINEDUC"

    def test_parses_entity_name(self):
        body = "Entidad: Ministerio de Educación\nPresupuesto: Q 5,000,000"
        result = self._parse(body)
        assert result.entity_name == "Ministerio de Educación"

    def test_parses_budget_amount(self):
        body = "Presupuesto: Q 5,000,000\nAño: 2024"
        result = self._parse(body)
        assert result.budget_amount == "Q 5,000,000"

    def test_model_roundtrip(self):
        from openquery.models.gt.minfin import MinfinResult

        r = MinfinResult(search_term="MINEDUC", entity_name="MINEDUC GT", budget_amount="Q 5M")
        data = r.model_dump_json()
        r2 = MinfinResult.model_validate_json(data)
        assert r2.budget_amount == "Q 5M"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.minfin import MinfinResult

        r = MinfinResult(search_term="test", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestMinfinSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.minfin import MinfinSource

        meta = MinfinSource().meta()
        assert meta.name == "gt.minfin"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.gt.minfin import MinfinSource

        src = MinfinSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
