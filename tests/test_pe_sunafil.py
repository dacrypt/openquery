"""Unit tests for Peru SUNAFIL labor inspections source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.sunafil import SunafilInspeccion, SunafilResult
from openquery.sources.pe.sunafil import SunafilSource


class TestSunafilResult:
    """Test SunafilResult model."""

    def test_default_values(self):
        data = SunafilResult()
        assert data.ruc == ""
        assert data.employer_name == ""
        assert data.inspections_count == 0
        assert data.sanctions == []
        assert data.inspections == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SunafilResult(
            ruc="20123456789",
            employer_name="EMPRESA SAC",
            inspections_count=2,
            sanctions=["S/.5000"],
        )
        json_str = data.model_dump_json()
        restored = SunafilResult.model_validate_json(json_str)
        assert restored.ruc == "20123456789"
        assert restored.employer_name == "EMPRESA SAC"
        assert restored.inspections_count == 2
        assert restored.sanctions == ["S/.5000"]

    def test_audit_excluded_from_json(self):
        data = SunafilResult(ruc="20123456789", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_inspeccion_default_values(self):
        inspeccion = SunafilInspeccion()
        assert inspeccion.numero == ""
        assert inspeccion.fecha == ""
        assert inspeccion.materia == ""
        assert inspeccion.resultado == ""
        assert inspeccion.sancion == ""


class TestSunafilSourceMeta:
    """Test SunafilSource metadata."""

    def test_meta_name(self):
        source = SunafilSource()
        assert source.meta().name == "pe.sunafil"

    def test_meta_country(self):
        source = SunafilSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = SunafilSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SunafilSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SunafilSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SunafilSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SunafilSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SunafilSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str, table_rows: list[tuple] | None = None) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text

        if table_rows:
            mock_rows = []
            for row_cells in table_rows:
                mock_row = MagicMock()
                mock_cells = []
                for text in row_cells:
                    mock_cell = MagicMock()
                    mock_cell.inner_text.return_value = text
                    mock_cells.append(mock_cell)
                mock_row.query_selector_all.return_value = mock_cells
                mock_rows.append(mock_row)
            mock_page.query_selector_all.return_value = mock_rows
        else:
            mock_page.query_selector_all.return_value = []

        return mock_page

    def test_parse_employer_name_from_body(self):
        source = SunafilSource()
        page = self._make_page(
            "Razón Social: EMPRESA TEST SAC\nRUC: 20123456789\n2 inspecciones encontradas\n"
        )
        result = source._parse_result(page, "20123456789")
        assert result.ruc == "20123456789"
        assert result.employer_name == "EMPRESA TEST SAC"

    def test_parse_inspections_from_table(self):
        source = SunafilSource()
        page = self._make_page(
            "Resultados",
            table_rows=[
                ("001-2023", "15/03/2023", "Seguridad y Salud", "INFRACCION", "S/.3000"),
                ("002-2023", "20/06/2023", "Relaciones Laborales", "ADVERTENCIA", ""),
            ],
        )
        result = source._parse_result(page, "20123456789")
        assert result.inspections_count == 2
        assert result.inspections[0].numero == "001-2023"
        assert result.inspections[0].sancion == "S/.3000"
        assert result.sanctions == ["S/.3000"]

    def test_parse_count_fallback_from_text(self):
        source = SunafilSource()
        page = self._make_page("Se encontraron 5 inspecciones registradas.")
        result = source._parse_result(page, "20123456789")
        assert result.inspections_count == 5

    def test_parse_ruc_preserved(self):
        source = SunafilSource()
        page = self._make_page("Sin resultados")
        result = source._parse_result(page, "20999999999")
        assert result.ruc == "20999999999"
