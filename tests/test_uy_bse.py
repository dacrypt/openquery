"""Tests for uy.bse — Uruguay BSE mandatory vehicle insurance source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestUyBseParseResult:
    def _parse(self, body_text: str, placa: str = "ABC1234"):
        from openquery.sources.uy.bse import UyBseSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = UyBseSource()
        return src._parse_result(page, placa)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.insurance_status == ""
        assert result.policy_valid == ""

    def test_placa_preserved(self):
        result = self._parse("", placa="ABC1234")
        assert result.placa == "ABC1234"

    def test_insurance_status_parsed(self):
        result = self._parse("Estado: Vigente\nVigencia: 2026-12-31")
        assert result.insurance_status == "Vigente"

    def test_policy_valid_parsed(self):
        result = self._parse("Vigencia: 2026-12-31")
        assert result.policy_valid == "2026-12-31"

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.uy.bse import UyBseSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Vigente", "2027-06-30"])]
        src = UyBseSource()
        result = src._parse_result(page, "ABC1234")
        assert result.insurance_status == "Vigente"
        assert result.policy_valid == "2027-06-30"

    def test_model_roundtrip(self):
        from openquery.models.uy.bse import UyBseResult

        r = UyBseResult(placa="ABC1234", insurance_status="Vigente", policy_valid="2027-06-30")
        data = r.model_dump_json()
        r2 = UyBseResult.model_validate_json(data)
        assert r2.placa == "ABC1234"
        assert r2.insurance_status == "Vigente"

    def test_audit_excluded_from_json(self):
        from openquery.models.uy.bse import UyBseResult

        r = UyBseResult(placa="ABC1234", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestUyBseSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.bse import UyBseSource

        meta = UyBseSource().meta()
        assert meta.name == "uy.bse"
        assert meta.country == "UY"
        assert DocumentType.PLATE in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_plate_raises(self):
        from openquery.sources.uy.bse import UyBseSource

        src = UyBseSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))
