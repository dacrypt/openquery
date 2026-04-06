"""Unit tests for Argentina AFIP monotributo source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.afip_monotributo import AfipMonotributoResult
from openquery.sources.ar.afip_monotributo import AfipMonotributoSource


class TestAfipMonotributoResult:
    """Test AfipMonotributoResult model."""

    def test_default_values(self):
        data = AfipMonotributoResult()
        assert data.cuit == ""
        assert data.taxpayer_name == ""
        assert data.category == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = AfipMonotributoResult(
            cuit="20-12345678-9",
            taxpayer_name="GOMEZ CARLOS",
            category="Categoría D",
            status="ACTIVO",
            details={"Categoría": "D"},
        )
        json_str = data.model_dump_json()
        restored = AfipMonotributoResult.model_validate_json(json_str)
        assert restored.cuit == "20-12345678-9"
        assert restored.taxpayer_name == "GOMEZ CARLOS"
        assert restored.category == "Categoría D"
        assert restored.status == "ACTIVO"

    def test_audit_excluded_from_json(self):
        data = AfipMonotributoResult(cuit="20-12345678-9", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestAfipMonotributoSourceMeta:
    """Test AfipMonotributoSource metadata."""

    def test_meta_name(self):
        source = AfipMonotributoSource()
        assert source.meta().name == "ar.afip_monotributo"

    def test_meta_country(self):
        source = AfipMonotributoSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = AfipMonotributoSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = AfipMonotributoSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = AfipMonotributoSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = AfipMonotributoSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = AfipMonotributoSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = AfipMonotributoSource()
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

    def test_parse_cuit_preserved(self):
        source = AfipMonotributoSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "20-12345678-9")
        assert result.cuit == "20-12345678-9"

    def test_parse_from_body_text(self):
        source = AfipMonotributoSource()
        page = self._make_page(
            "Nombre: GOMEZ CARLOS\nCategoría: D\nCondición: ACTIVO\n"
        )
        result = source._parse_result(page, "20-12345678-9")
        assert result.taxpayer_name == "GOMEZ CARLOS"
        assert result.category == "D"
        assert result.status == "ACTIVO"

    def test_parse_from_table(self):
        source = AfipMonotributoSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Denominación", "RODRIGUEZ ANA"),
                ("Categoría", "Categoría H"),
                ("Estado", "ACTIVO"),
            ],
        )
        result = source._parse_result(page, "27-87654321-3")
        assert result.taxpayer_name == "RODRIGUEZ ANA"
        assert result.category == "Categoría H"
        assert result.status == "ACTIVO"
        assert result.details["Denominación"] == "RODRIGUEZ ANA"

    def test_parse_empty_body(self):
        source = AfipMonotributoSource()
        page = self._make_page("")
        result = source._parse_result(page, "20-12345678-9")
        assert result.cuit == "20-12345678-9"
        assert result.taxpayer_name == ""
