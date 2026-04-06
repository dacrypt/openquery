"""Tests for hn.cnbs — Honduras CNBS banking supervisor source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnCnbsParseResult:
    def _parse(self, body_text: str, search_term: str = "Banco Atlantida"):
        from openquery.sources.hn.cnbs import HnCnbsSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = HnCnbsSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.entity_name == ""
        assert result.entity_type == ""
        assert result.status == ""

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Banco Atlantida")
        assert result.search_term == "Banco Atlantida"

    def test_entity_name_parsed(self):
        result = self._parse("Entidad: Banco Atlantida SA\nEstado: Autorizado")
        assert result.entity_name == "Banco Atlantida SA"

    def test_status_parsed(self):
        result = self._parse("Estado: Activo")
        assert result.status == "Activo"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.hn.cnbs import HnCnbsSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Banco HN", "Banco", "Activo"])]  # noqa: E501
        src = HnCnbsSource()
        result = src._parse_result(page, "Banco HN")
        assert result.entity_name == "Banco HN"
        assert result.entity_type == "Banco"
        assert result.status == "Activo"

    def test_model_roundtrip(self):
        from openquery.models.hn.cnbs import HnCnbsResult

        r = HnCnbsResult(
            search_term="Banco Atlantida",
            entity_name="Banco Atlantida SA",
            entity_type="Banco",
            status="Autorizado",
        )
        data = r.model_dump_json()
        r2 = HnCnbsResult.model_validate_json(data)
        assert r2.entity_name == "Banco Atlantida SA"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.cnbs import HnCnbsResult

        r = HnCnbsResult(search_term="Banco X", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestHnCnbsSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.cnbs import HnCnbsSource

        meta = HnCnbsSource().meta()
        assert meta.name == "hn.cnbs"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.hn.cnbs import HnCnbsSource

        src = HnCnbsSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
