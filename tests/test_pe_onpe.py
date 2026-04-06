"""Unit tests for Peru ONPE electoral processes source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.onpe import OnpeResult
from openquery.sources.pe.onpe import OnpeSource


class TestOnpeResult:
    """Test OnpeResult model."""

    def test_default_values(self):
        data = OnpeResult()
        assert data.dni == ""
        assert data.nombre == ""
        assert data.electoral_location == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OnpeResult(
            dni="12345678",
            nombre="ANA TORRES",
            electoral_location="LOCAL 001 - LIMA",
            details={"Local": "LOCAL 001"},
        )
        json_str = data.model_dump_json()
        restored = OnpeResult.model_validate_json(json_str)
        assert restored.dni == "12345678"
        assert restored.nombre == "ANA TORRES"
        assert restored.electoral_location == "LOCAL 001 - LIMA"

    def test_audit_excluded_from_json(self):
        data = OnpeResult(dni="12345678", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestOnpeSourceMeta:
    """Test OnpeSource metadata."""

    def test_meta_name(self):
        source = OnpeSource()
        assert source.meta().name == "pe.onpe"

    def test_meta_country(self):
        source = OnpeSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = OnpeSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = OnpeSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = OnpeSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = OnpeSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = OnpeSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = OnpeSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


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

    def test_parse_dni_preserved(self):
        source = OnpeSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "12345678")
        assert result.dni == "12345678"

    def test_parse_from_body_text(self):
        source = OnpeSource()
        page = self._make_page(
            "Nombre: ANA TORRES\nLocal de Votación: COLEGIO LIMA 001\n"
        )
        result = source._parse_result(page, "12345678")
        assert result.nombre == "ANA TORRES"
        assert result.electoral_location == "COLEGIO LIMA 001"

    def test_parse_from_table(self):
        source = OnpeSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Nombre", "CARLOS GARCIA"),
                ("Local de Votación", "IE SAN MARTIN"),
            ],
        )
        result = source._parse_result(page, "87654321")
        assert result.nombre == "CARLOS GARCIA"
        assert result.electoral_location == "IE SAN MARTIN"
        assert result.details["Nombre"] == "CARLOS GARCIA"

    def test_parse_empty_body(self):
        source = OnpeSource()
        page = self._make_page("")
        result = source._parse_result(page, "12345678")
        assert result.dni == "12345678"
        assert result.nombre == ""
