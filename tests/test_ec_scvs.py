"""Unit tests for Ecuador SCVS company registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.scvs import ScvsResult
from openquery.sources.ec.scvs import ScvsSource


class TestScvsResult:
    """Test ScvsResult model."""

    def test_default_values(self):
        data = ScvsResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.ruc == ""
        assert data.status == ""
        assert data.legal_representative == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ScvsResult(
            search_term="ACME",
            company_name="ACME S.A.",
            ruc="1790012345001",
            status="ACTIVA",
            legal_representative="JUAN PEREZ",
        )
        json_str = data.model_dump_json()
        restored = ScvsResult.model_validate_json(json_str)
        assert restored.search_term == "ACME"
        assert restored.company_name == "ACME S.A."
        assert restored.ruc == "1790012345001"
        assert restored.status == "ACTIVA"

    def test_audit_excluded_from_json(self):
        data = ScvsResult(search_term="ACME", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestScvsSourceMeta:
    """Test ScvsSource metadata."""

    def test_meta_name(self):
        source = ScvsSource()
        assert source.meta().name == "ec.scvs"

    def test_meta_country(self):
        source = ScvsSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = ScvsSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = ScvsSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = ScvsSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ScvsSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = ScvsSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = ScvsSource()
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
        source = ScvsSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "ACME")
        assert result.search_term == "ACME"

    def test_parse_from_body_text(self):
        source = ScvsSource()
        page = self._make_page(
            "Razón Social: ACME S.A.\nRUC: 1790012345001\n"
            "Estado: ACTIVA\nRepresentante: JUAN PEREZ\n"
        )
        result = source._parse_result(page, "ACME")
        assert result.company_name == "ACME S.A."
        assert result.ruc == "1790012345001"
        assert result.status == "ACTIVA"
        assert result.legal_representative == "JUAN PEREZ"

    def test_parse_from_table(self):
        source = ScvsSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Razón Social", "BETA CIA. LTDA."),
                ("RUC", "0990123456001"),
                ("Estado", "INACTIVA"),
                ("Representante Legal", "ANA TORRES"),
            ],
        )
        result = source._parse_result(page, "BETA")
        assert result.company_name == "BETA CIA. LTDA."
        assert result.ruc == "0990123456001"
        assert result.status == "INACTIVA"
        assert result.legal_representative == "ANA TORRES"
        assert result.details["RUC"] == "0990123456001"
