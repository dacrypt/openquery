"""Unit tests for Chile SERNAC consumer complaints source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.sernac import SernacResult
from openquery.sources.cl.sernac import SernacSource


class TestSernacResult:
    """Test SernacResult model."""

    def test_default_values(self):
        data = SernacResult()
        assert data.company_name == ""
        assert data.total_complaints == ""
        assert data.resolution_rate == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SernacResult(
            company_name="EMPRESA ABC",
            total_complaints="120",
            resolution_rate="85%",
            details={"Reclamos": "120"},
        )
        json_str = data.model_dump_json()
        restored = SernacResult.model_validate_json(json_str)
        assert restored.company_name == "EMPRESA ABC"
        assert restored.total_complaints == "120"
        assert restored.resolution_rate == "85%"

    def test_audit_excluded_from_json(self):
        data = SernacResult(company_name="EMPRESA ABC", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSernacSourceMeta:
    """Test SernacSource metadata."""

    def test_meta_name(self):
        source = SernacSource()
        assert source.meta().name == "cl.sernac"

    def test_meta_country(self):
        source = SernacSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = SernacSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SernacSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SernacSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SernacSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SernacSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SernacSource()
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

    def test_parse_company_name_preserved(self):
        source = SernacSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "EMPRESA ABC")
        assert result.company_name == "EMPRESA ABC"

    def test_parse_from_body_text(self):
        source = SernacSource()
        page = self._make_page("Total Reclamos: 120\nTasa de Resolución: 85%\n")
        result = source._parse_result(page, "EMPRESA ABC")
        assert result.total_complaints == "120"
        assert result.resolution_rate == "85%"

    def test_parse_from_table(self):
        source = SernacSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Total Reclamos", "250"),
                ("Tasa Resolución", "92%"),
            ],
        )
        result = source._parse_result(page, "FALABELLA")
        assert result.total_complaints == "250"
        assert result.resolution_rate == "92%"
        assert result.details["Total Reclamos"] == "250"

    def test_parse_empty_body(self):
        source = SernacSource()
        page = self._make_page("")
        result = source._parse_result(page, "EMPRESA ABC")
        assert result.company_name == "EMPRESA ABC"
        assert result.total_complaints == ""
