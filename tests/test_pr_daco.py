"""Tests for pr.daco — Puerto Rico DACO consumer affairs source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestPrDacoParseResult:
    def _parse(self, body_text: str, search_term: str = "Empresa Ejemplo"):
        from openquery.sources.pr.daco import PrDacoSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        page.query_selector_all.return_value = []
        src = PrDacoSource()
        return src._parse_result(page, search_term)

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.company_name == ""
        assert result.license_status == ""
        assert result.complaints_count == 0

    def test_search_term_preserved(self):
        result = self._parse("", search_term="Empresa Ejemplo")
        assert result.search_term == "Empresa Ejemplo"

    def test_company_name_parsed(self):
        result = self._parse("Empresa: Tienda Ejemplo Inc\nLicencia: Activa")
        assert result.company_name == "Tienda Ejemplo Inc"

    def test_license_status_parsed(self):
        result = self._parse("Licencia: Activa")
        assert result.license_status == "Activa"

    def test_complaints_count_parsed(self):
        result = self._parse("Querellas: 3")
        assert result.complaints_count == 3

    def test_table_rows_parsed(self):
        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        def make_row(texts):
            r = MagicMock()
            r.query_selector_all.return_value = [make_cell(t) for t in texts]
            return r

        from openquery.sources.pr.daco import PrDacoSource

        page = MagicMock()
        page.inner_text.return_value = ""
        page.query_selector_all.return_value = [make_row([]), make_row(["Tienda XYZ", "Activa", "2"])]  # noqa: E501
        src = PrDacoSource()
        result = src._parse_result(page, "Tienda XYZ")
        assert result.company_name == "Tienda XYZ"
        assert result.license_status == "Activa"
        assert result.complaints_count == 2

    def test_model_roundtrip(self):
        from openquery.models.pr.daco import PrDacoResult

        r = PrDacoResult(
            search_term="Empresa Ejemplo",
            company_name="Tienda Ejemplo Inc",
            license_status="Activa",
            complaints_count=3,
        )
        data = r.model_dump_json()
        r2 = PrDacoResult.model_validate_json(data)
        assert r2.company_name == "Tienda Ejemplo Inc"
        assert r2.complaints_count == 3

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.daco import PrDacoResult

        r = PrDacoResult(search_term="Empresa X", audit=b"pdf")
        assert "audit" not in r.model_dump_json()


class TestPrDacoSourceMeta:
    def test_meta(self):
        from openquery.sources.pr.daco import PrDacoSource

        meta = PrDacoSource().meta()
        assert meta.name == "pr.daco"
        assert meta.country == "PR"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_search_raises(self):
        from openquery.sources.pr.daco import PrDacoSource

        src = PrDacoSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
