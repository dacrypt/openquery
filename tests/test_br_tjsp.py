"""Tests for br.tjsp — São Paulo court cases lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestResult:
    """Test TjspResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.br.tjsp import TjspResult

        r = TjspResult()
        assert r.search_term == ""
        assert r.total_cases == 0
        assert r.cases == []
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.br.tjsp import TjspResult

        r = TjspResult(search_term="PETROBRAS", audit={"screenshot": "data"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "PETROBRAS" in dumped

    def test_json_roundtrip(self):
        from openquery.models.br.tjsp import TjspResult

        r = TjspResult(
            search_term="PETROBRAS",
            total_cases=5,
            cases=[{"col_0": "1234567", "col_1": "Em andamento"}],
            details={"Tribunal": "TJSP"},
        )
        r2 = TjspResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "PETROBRAS"
        assert r2.total_cases == 5
        assert len(r2.cases) == 1
        assert r2.cases[0]["col_0"] == "1234567"

    def test_queried_at_default(self):
        from openquery.models.br.tjsp import TjspResult

        before = datetime.now()
        r = TjspResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestSourceMeta:
    """Test br.tjsp source metadata."""

    def test_meta_name(self):
        from openquery.sources.br.tjsp import TjspSource

        meta = TjspSource().meta()
        assert meta.name == "br.tjsp"

    def test_meta_country(self):
        from openquery.sources.br.tjsp import TjspSource

        meta = TjspSource().meta()
        assert meta.country == "BR"

    def test_meta_requires_browser(self):
        from openquery.sources.br.tjsp import TjspSource

        meta = TjspSource().meta()
        assert meta.requires_browser is True
        assert meta.requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.br.tjsp import TjspSource

        meta = TjspSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.tjsp import TjspSource

        meta = TjspSource().meta()
        assert meta.rate_limit_rpm == 10


class TestParseResult:
    """Test _parse_result with mocked page."""

    def _make_source(self):
        from openquery.sources.br.tjsp import TjspSource

        return TjspSource()

    def _make_page(self, text: str):
        page = MagicMock()
        page.inner_text.return_value = text
        page.query_selector_all.return_value = []
        return page

    def test_not_found_returns_empty(self):
        src = self._make_source()
        page = self._make_page("Nenhum processo encontrado para a pesquisa")
        result = src._parse_result(page, "INEXISTENTE")
        assert result.search_term == "INEXISTENTE"
        assert result.total_cases == 0
        assert result.cases == []

    def test_search_term_preserved(self):
        src = self._make_source()
        page = self._make_page("Resultado da consulta")
        result = src._parse_result(page, "PETROBRAS")
        assert result.search_term == "PETROBRAS"

    def test_total_cases_parsed(self):
        src = self._make_source()
        page = self._make_page("Foram encontrados 3 processos para a pesquisa")
        result = src._parse_result(page, "PETROBRAS")
        assert result.total_cases == 3

    def test_details_from_key_value(self):
        src = self._make_source()
        page = self._make_page("Tribunal: TJSP\nClasse: Ação Civil")
        result = src._parse_result(page, "PETROBRAS")
        assert "Tribunal" in result.details

    def test_query_missing_term_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.br.tjsp import TjspSource

        src = TjspSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        from unittest.mock import patch

        from openquery.models.br.tjsp import TjspResult
        from openquery.sources.br.tjsp import TjspSource

        src = TjspSource()
        mock_result = TjspResult(search_term="PETROBRAS")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="PETROBRAS"))
            m.assert_called_once_with("PETROBRAS", audit=False)
