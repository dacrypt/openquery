"""Unit tests for Ecuador Supercias expediente corporate filings source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.supercias_expediente import SuperciasExpedienteResult
from openquery.sources.ec.supercias_expediente import SuperciasExpedienteSource


class TestSuperciasExpedienteResult:
    """Test SuperciasExpedienteResult model."""

    def test_default_values(self):
        data = SuperciasExpedienteResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.ruc == ""
        assert data.total_filings == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SuperciasExpedienteResult(
            search_term="EMPRESA XYZ",
            company_name="EMPRESA XYZ SA",
            ruc="0912345678001",
            total_filings="12",
            details={"Expedientes": "12"},
        )
        json_str = data.model_dump_json()
        restored = SuperciasExpedienteResult.model_validate_json(json_str)
        assert restored.search_term == "EMPRESA XYZ"
        assert restored.company_name == "EMPRESA XYZ SA"
        assert restored.ruc == "0912345678001"
        assert restored.total_filings == "12"

    def test_audit_excluded_from_json(self):
        data = SuperciasExpedienteResult(search_term="EMPRESA XYZ", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSuperciasExpedienteSourceMeta:
    """Test SuperciasExpedienteSource metadata."""

    def test_meta_name(self):
        source = SuperciasExpedienteSource()
        assert source.meta().name == "ec.supercias_expediente"

    def test_meta_country(self):
        source = SuperciasExpedienteSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = SuperciasExpedienteSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SuperciasExpedienteSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SuperciasExpedienteSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SuperciasExpedienteSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SuperciasExpedienteSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SuperciasExpedienteSource()
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
        source = SuperciasExpedienteSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "EMPRESA XYZ")
        assert result.search_term == "EMPRESA XYZ"

    def test_parse_from_body_text(self):
        source = SuperciasExpedienteSource()
        page = self._make_page(
            "Empresa: EMPRESA XYZ SA\nRUC: 0912345678001\nTotal Expedientes: 12\n"
        )
        result = source._parse_result(page, "EMPRESA XYZ")
        assert result.company_name == "EMPRESA XYZ SA"
        assert result.ruc == "0912345678001"
        assert result.total_filings == "12"

    def test_parse_from_table(self):
        source = SuperciasExpedienteSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Razón Social", "CONSTRUCTORA ABC SA"),
                ("RUC", "1712345678001"),
                ("Total Expedientes", "7"),
            ],
        )
        result = source._parse_result(page, "CONSTRUCTORA ABC")
        assert result.company_name == "CONSTRUCTORA ABC SA"
        assert result.ruc == "1712345678001"
        assert result.total_filings == "7"
        assert result.details["Razón Social"] == "CONSTRUCTORA ABC SA"

    def test_parse_empty_body(self):
        source = SuperciasExpedienteSource()
        page = self._make_page("")
        result = source._parse_result(page, "EMPRESA XYZ")
        assert result.search_term == "EMPRESA XYZ"
        assert result.company_name == ""
