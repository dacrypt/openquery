"""Unit tests for Chile SMA environmental sanctions source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.sma import SmaResult
from openquery.sources.cl.sma import SmaSource


class TestSmaResult:
    """Test SmaResult model."""

    def test_default_values(self):
        data = SmaResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.total_sanctions == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SmaResult(
            search_term="CODELCO",
            company_name="CODELCO CHILE",
            total_sanctions="3",
            details={"Sanciones": "3"},
        )
        json_str = data.model_dump_json()
        restored = SmaResult.model_validate_json(json_str)
        assert restored.search_term == "CODELCO"
        assert restored.company_name == "CODELCO CHILE"
        assert restored.total_sanctions == "3"

    def test_audit_excluded_from_json(self):
        data = SmaResult(search_term="CODELCO", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSmaSourceMeta:
    """Test SmaSource metadata."""

    def test_meta_name(self):
        source = SmaSource()
        assert source.meta().name == "cl.sma"

    def test_meta_country(self):
        source = SmaSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = SmaSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SmaSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SmaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SmaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SmaSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SmaSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str, table_rows: list[tuple] | None = None) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text

        if table_rows:
            mock_rows = []
            for label, value in table_rows:
                mock_row = MagicMock()
                mock_cells = []
                for text in (label, value):
                    mock_cell = MagicMock()
                    mock_cell.inner_text.return_value = text
                    mock_cells.append(mock_cell)
                mock_row.query_selector_all.return_value = mock_cells
                mock_rows.append(mock_row)
            mock_page.query_selector_all.return_value = mock_rows
        else:
            mock_page.query_selector_all.return_value = []

        return mock_page

    def test_parse_search_term_preserved(self):
        source = SmaSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "CODELCO")
        assert result.search_term == "CODELCO"

    def test_parse_from_body_text(self):
        source = SmaSource()
        page = self._make_page(
            "Empresa: CODELCO CHILE\nTotal Sanciones: 3\n"
        )
        result = source._parse_result(page, "CODELCO")
        assert result.company_name == "CODELCO CHILE"
        assert result.total_sanctions == "3"

    def test_parse_from_table(self):
        source = SmaSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Razón Social", "EMPRESA MINERA SA"),
                ("Total Infracciones", "5"),
            ],
        )
        result = source._parse_result(page, "MINERA SA")
        assert result.company_name == "EMPRESA MINERA SA"
        assert result.total_sanctions == "5"
        assert result.details["Razón Social"] == "EMPRESA MINERA SA"

    def test_parse_empty_body(self):
        source = SmaSource()
        page = self._make_page("")
        result = source._parse_result(page, "CODELCO")
        assert result.search_term == "CODELCO"
        assert result.total_sanctions == ""
