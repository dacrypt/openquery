"""Unit tests for Chile Conservador de Bienes Raíces property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.conservador import ConservadorResult
from openquery.sources.cl.conservador import ConservadorSource


class TestConservadorResult:
    """Test ConservadorResult model."""

    def test_default_values(self):
        data = ConservadorResult()
        assert data.search_term == ""
        assert data.property_records == []
        assert data.mortgages == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ConservadorResult(
            search_term="GARCIA SANTIAGO",
            property_records=[{"Folio": "1234", "Descripcion": "Casa"}],
            mortgages=[{"Acreedor": "BANCO CHILE", "Monto": "50000000"}],
        )
        json_str = data.model_dump_json()
        restored = ConservadorResult.model_validate_json(json_str)
        assert restored.search_term == "GARCIA SANTIAGO"
        assert len(restored.property_records) == 1
        assert restored.property_records[0]["Folio"] == "1234"
        assert len(restored.mortgages) == 1

    def test_audit_excluded_from_json(self):
        data = ConservadorResult(search_term="GARCIA SANTIAGO", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_empty_records(self):
        data = ConservadorResult(search_term="SIN RESULTADO")
        assert data.property_records == []
        assert data.mortgages == []


class TestConservadorSourceMeta:
    """Test ConservadorSource metadata."""

    def test_meta_name(self):
        source = ConservadorSource()
        assert source.meta().name == "cl.conservador"

    def test_meta_country(self):
        source = ConservadorSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = ConservadorSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = ConservadorSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = ConservadorSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ConservadorSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = ConservadorSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = ConservadorSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page_with_tables(
        self,
        tables: list[dict] | None = None,
    ) -> MagicMock:
        """Build a mock page with zero or more tables, each with headers and body rows."""
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_tables = []
        for table_spec in tables or []:
            mock_table = MagicMock()
            headers = table_spec.get("headers", [])
            rows = table_spec.get("rows", [])

            # thead headers
            header_els = []
            for h in headers:
                el = MagicMock()
                el.inner_text.return_value = h
                header_els.append(el)
            mock_table.query_selector_all.side_effect = lambda sel, _h=header_els, _r=rows: (
                _h if "thead" in sel or "first-child th" in sel else _build_body_rows(_r)
            )
            mock_tables.append(mock_table)

        mock_page.query_selector_all.return_value = mock_tables
        return mock_page

    def test_parse_search_term_preserved(self):
        source = ConservadorSource()
        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = []
        result = source._parse_result(mock_page, "GARCIA SANTIAGO")
        assert result.search_term == "GARCIA SANTIAGO"

    def test_parse_empty_tables(self):
        source = ConservadorSource()
        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = []
        result = source._parse_result(mock_page, "GARCIA SANTIAGO")
        assert result.property_records == []
        assert result.mortgages == []

    def test_result_model_stores_records(self):
        data = ConservadorResult(
            search_term="PEREZ VALPARAISO",
            property_records=[{"0": "Lote 5", "1": "Parcela"}],
        )
        assert data.property_records[0]["0"] == "Lote 5"

    def test_result_model_stores_mortgages(self):
        data = ConservadorResult(
            search_term="PEREZ VALPARAISO",
            mortgages=[{"0": "HIPOTECA BCI", "1": "25000000"}],
        )
        assert data.mortgages[0]["0"] == "HIPOTECA BCI"


def _build_body_rows(rows: list[list[str]]):
    mock_rows = []
    for row_cells in rows:
        mock_row = MagicMock()
        cells = []
        for text in row_cells:
            cell = MagicMock()
            cell.inner_text.return_value = text
            cells.append(cell)
        mock_row.query_selector_all.return_value = cells
        mock_rows.append(mock_row)
    return mock_rows
