"""Tests for uy.ine — Uruguay INE statistics portal source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestUyIneParseResult:
    def _parse(self, body_text: str, indicator: str = "IPC"):
        from openquery.sources.uy.ine import UyIneSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = UyIneSource()
        return src._parse_result(page, indicator)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.value == ""
        assert result.period == ""

    def test_indicator_preserved(self):
        result = self._parse("", indicator="IPC")
        assert result.indicator == "IPC"

    def test_value_parsed(self):
        result = self._parse("Valor: 105.3\nPeriodo: Enero 2026")
        assert result.value == "105.3"

    def test_period_parsed(self):
        result = self._parse("Periodo: Enero 2026")
        assert result.period == "Enero 2026"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.uy.ine import UyIneSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["107.2", "Feb 2026"])]
        src = UyIneSource()
        result = src._parse_result(page, "IPC")
        assert result.value == "107.2"
        assert result.period == "Feb 2026"

    def test_model_roundtrip(self):
        from openquery.models.uy.ine import UyIneResult

        r = UyIneResult(indicator="IPC", value="105.3", period="Enero 2026")
        data = r.model_dump_json()
        r2 = UyIneResult.model_validate_json(data)
        assert r2.indicator == "IPC"
        assert r2.value == "105.3"

    def test_audit_excluded_from_json(self):
        from openquery.models.uy.ine import UyIneResult

        r = UyIneResult(indicator="IPC", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestUyIneSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.ine import UyIneSource

        meta = UyIneSource().meta()
        assert meta.name == "uy.ine"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_indicator_raises(self):
        from openquery.sources.uy.ine import UyIneSource

        src = UyIneSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
