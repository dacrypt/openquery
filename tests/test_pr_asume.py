"""Tests for pr.asume — Puerto Rico ASUME child support source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPrAsumeParseResult:
    def _parse(self, body_text: str, case_number: str = "CASE-001"):
        from openquery.sources.pr.asume import PrAsumeSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = PrAsumeSource()
        return src._parse_result(page, case_number)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.status == ""

    def test_case_number_preserved(self):
        result = self._parse("", case_number="CASE-001")
        assert result.case_number == "CASE-001"

    def test_status_parsed(self):
        result = self._parse("Estado: Activo")
        assert result.status == "Activo"

    def test_estatus_parsed(self):
        result = self._parse("Estatus: Cerrado")
        assert result.status == "Cerrado"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.pr.asume import PrAsumeSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Pendiente"])]
        src = PrAsumeSource()
        result = src._parse_result(page, "CASE-001")
        assert result.status == "Pendiente"

    def test_model_roundtrip(self):
        from openquery.models.pr.asume import PrAsumeResult

        r = PrAsumeResult(case_number="CASE-001", status="Activo")
        data = r.model_dump_json()
        r2 = PrAsumeResult.model_validate_json(data)
        assert r2.case_number == "CASE-001"
        assert r2.status == "Activo"

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.asume import PrAsumeResult

        r = PrAsumeResult(case_number="CASE-001", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestPrAsumeSourceMeta:
    def test_meta(self):
        from openquery.sources.pr.asume import PrAsumeSource

        meta = PrAsumeSource().meta()
        assert meta.name == "pr.asume"
        assert meta.country == "PR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_case_number_raises(self):
        from openquery.sources.pr.asume import PrAsumeSource

        src = PrAsumeSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
