"""Tests for hn.ihss — Honduras IHSS social security source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestHnIhssParseResult:
    def _parse(self, body_text: str, identidad: str = "0801199900000"):
        from openquery.sources.hn.ihss import HnIhssSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = HnIhssSource()
        return src._parse_result(page, identidad)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.affiliation_status == ""
        assert result.employer == ""

    def test_identidad_preserved(self):
        result = self._parse("", identidad="0801199900000")
        assert result.identidad == "0801199900000"

    def test_affiliation_status_parsed(self):
        result = self._parse("Estado: Afiliado\nEmpleador: Empresa SA")
        assert result.affiliation_status == "Afiliado"

    def test_employer_parsed(self):
        result = self._parse("Empleador: Empresa Ejemplo SA")
        assert result.employer == "Empresa Ejemplo SA"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.hn.ihss import HnIhssSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Afiliado", "Empresa HN SA"])]  # noqa: E501
        src = HnIhssSource()
        result = src._parse_result(page, "0801199900000")
        assert result.affiliation_status == "Afiliado"
        assert result.employer == "Empresa HN SA"

    def test_model_roundtrip(self):
        from openquery.models.hn.ihss import HnIhssResult

        r = HnIhssResult(
            identidad="0801199900000",
            affiliation_status="Afiliado",
            employer="Empresa HN SA",
        )
        data = r.model_dump_json()
        r2 = HnIhssResult.model_validate_json(data)
        assert r2.identidad == "0801199900000"
        assert r2.affiliation_status == "Afiliado"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.ihss import HnIhssResult

        r = HnIhssResult(identidad="0801199900000", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestHnIhssSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.ihss import HnIhssSource

        meta = HnIhssSource().meta()
        assert meta.name == "hn.ihss"
        assert meta.country == "HN"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_identidad_raises(self):
        from openquery.sources.hn.ihss import HnIhssSource

        src = HnIhssSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number=""))
