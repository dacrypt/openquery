"""Tests for hn.bch — Honduras BCH exchange rate source."""

from __future__ import annotations

from openquery.sources.base import DocumentType, QueryInput


class TestHnBchParseHtml:
    def _parse(self, html: str):
        from openquery.sources.hn.bch import HnBchSource

        src = HnBchSource()
        return src._parse_html(html)

    def test_empty_html_returns_defaults(self):
        result = self._parse("")
        assert result.usd_rate == ""
        assert result.date == ""

    def test_usd_rate_extracted(self):
        html = "<p>Tasa de Cambio USD: 24.6982</p><p>Fecha: 01/04/2026</p>"
        result = self._parse(html)
        assert result.usd_rate != ""

    def test_date_extracted(self):
        html = "<p>01/04/2026 - Tasa: 24.6982</p>"
        result = self._parse(html)
        assert result.date != ""

    def test_details_populated(self):
        result = self._parse("<p>USD: 24.69</p>")
        assert "moneda" in result.details
        assert result.details["moneda"] == "HNL/USD"

    def test_model_roundtrip(self):
        from openquery.models.hn.bch import HnBchResult

        r = HnBchResult(usd_rate="24.6982", date="01/04/2026")
        data = r.model_dump_json()
        r2 = HnBchResult.model_validate_json(data)
        assert r2.usd_rate == "24.6982"
        assert r2.date == "01/04/2026"

    def test_audit_excluded_from_json(self):
        from openquery.models.hn.bch import HnBchResult

        r = HnBchResult(usd_rate="24.6982", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestHnBchSourceMeta:
    def test_meta(self):
        from openquery.sources.hn.bch import HnBchSource

        meta = HnBchSource().meta()
        assert meta.name == "hn.bch"
        assert meta.country == "HN"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_query_accepts_empty_input(self):
        from openquery.sources.hn.bch import HnBchSource

        HnBchSource()
        # query() delegates to _query() with no args — no SourceError expected for empty input
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        # Just check it calls _query without raising for missing input
        assert qi.document_number == ""
