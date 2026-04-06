"""Unit tests for Chile FONASA health affiliation source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.fonasa import FonasaResult
from openquery.sources.cl.fonasa import FonasaSource


class TestFonasaResult:
    """Test FonasaResult model."""

    def test_default_values(self):
        data = FonasaResult()
        assert data.rut == ""
        assert data.affiliation_status == ""
        assert data.tier == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = FonasaResult(
            rut="12345678-9",
            affiliation_status="AFILIADO",
            tier="B",
            details={"Tramo": "B"},
        )
        json_str = data.model_dump_json()
        restored = FonasaResult.model_validate_json(json_str)
        assert restored.rut == "12345678-9"
        assert restored.affiliation_status == "AFILIADO"
        assert restored.tier == "B"

    def test_audit_excluded_from_json(self):
        data = FonasaResult(rut="12345678-9", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestFonasaSourceMeta:
    """Test FonasaSource metadata."""

    def test_meta_name(self):
        source = FonasaSource()
        assert source.meta().name == "cl.fonasa"

    def test_meta_country(self):
        source = FonasaSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = FonasaSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = FonasaSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = FonasaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = FonasaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = FonasaSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = FonasaSource()
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

    def test_parse_rut_preserved(self):
        source = FonasaSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "12345678-9")
        assert result.rut == "12345678-9"

    def test_parse_from_body_text(self):
        source = FonasaSource()
        page = self._make_page("Estado Afiliación: AFILIADO\nTramo: B\n")
        result = source._parse_result(page, "12345678-9")
        assert result.affiliation_status == "AFILIADO"
        assert result.tier == "B"

    def test_parse_from_table(self):
        source = FonasaSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Estado Afiliacion", "AFILIADO"),
                ("Grupo", "C"),
            ],
        )
        result = source._parse_result(page, "12345678-9")
        assert result.affiliation_status == "AFILIADO"
        assert result.tier == "C"
        assert result.details["Grupo"] == "C"

    def test_parse_empty_body(self):
        source = FonasaSource()
        page = self._make_page("")
        result = source._parse_result(page, "12345678-9")
        assert result.rut == "12345678-9"
        assert result.affiliation_status == ""
