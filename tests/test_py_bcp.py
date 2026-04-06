"""Tests for py.bcp — Paraguay BCP central bank exchange rates source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.sources.base import DocumentType, QueryInput


class TestPyBcpParseResult:
    def _parse(self, body_text: str, rows=None):
        from openquery.sources.py.bcp import PyBcpSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        if rows is not None:
            page.query_selector_all.return_value = rows
        else:
            page.query_selector_all.return_value = []
        src = PyBcpSource()
        return src._parse_result(page)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.usd_rate == ""
        assert result.date == ""

    def test_usd_rate_from_body_text(self):
        result = self._parse("USD: 7500\nFecha: 2026-01-01")
        assert result.usd_rate == "7500"

    def test_usd_rate_from_table(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        rows = [make_row(["2026-01-01", "USD", "7520.00"])]
        result = self._parse("", rows=rows)
        assert result.usd_rate == "7520.00"

    def test_model_roundtrip(self):
        from openquery.models.py.bcp import PyBcpResult

        r = PyBcpResult(usd_rate="7500.00", date="2026-01-01")
        data = r.model_dump_json()
        r2 = PyBcpResult.model_validate_json(data)
        assert r2.usd_rate == "7500.00"
        assert r2.date == "2026-01-01"

    def test_audit_excluded_from_json(self):
        from openquery.models.py.bcp import PyBcpResult

        r = PyBcpResult(usd_rate="7500", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestPyBcpSourceMeta:
    def test_meta(self):
        from openquery.sources.py.bcp import PyBcpSource

        meta = PyBcpSource().meta()
        assert meta.name == "py.bcp"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_default_timeout(self):
        from openquery.sources.py.bcp import PyBcpSource

        src = PyBcpSource()
        assert src._timeout == 30.0

    def test_query_accepts_any_input(self):
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        assert qi.document_type == DocumentType.CUSTOM
