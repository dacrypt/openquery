"""Unit tests for Peru JNE electoral registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.jne import JneResult
from openquery.sources.pe.jne import JneSource


class TestJneResult:
    """Test JneResult model."""

    def test_default_values(self):
        data = JneResult()
        assert data.dni == ""
        assert data.nombre == ""
        assert data.electoral_district == ""
        assert data.voting_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = JneResult(
            dni="12345678",
            nombre="CARLOS GARCIA",
            electoral_district="LIMA",
            voting_status="HABILITADO",
            details={"Distrito": "LIMA"},
        )
        json_str = data.model_dump_json()
        restored = JneResult.model_validate_json(json_str)
        assert restored.dni == "12345678"
        assert restored.nombre == "CARLOS GARCIA"
        assert restored.electoral_district == "LIMA"
        assert restored.voting_status == "HABILITADO"

    def test_audit_excluded_from_json(self):
        data = JneResult(dni="12345678", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestJneSourceMeta:
    """Test JneSource metadata."""

    def test_meta_name(self):
        source = JneSource()
        assert source.meta().name == "pe.jne"

    def test_meta_country(self):
        source = JneSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = JneSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = JneSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = JneSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = JneSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = JneSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = JneSource()
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
        source = JneSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "12345678")
        assert result.dni == "12345678"

    def test_parse_from_body_text(self):
        source = JneSource()
        page = self._make_page(
            "Nombre: CARLOS GARCIA\nDistrito Electoral: LIMA\nEstado: HABILITADO\n"
        )
        result = source._parse_result(page, "12345678")
        assert result.nombre == "CARLOS GARCIA"
        assert result.electoral_district == "LIMA"
        assert result.voting_status == "HABILITADO"

    def test_parse_from_table(self):
        source = JneSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Nombre", "MARIA RIOS"),
                ("Circunscripción", "AREQUIPA"),
                ("Condición", "HABILITADO"),
            ],
        )
        result = source._parse_result(page, "87654321")
        assert result.nombre == "MARIA RIOS"
        assert result.electoral_district == "AREQUIPA"
        assert result.voting_status == "HABILITADO"
        assert result.details["Nombre"] == "MARIA RIOS"

    def test_parse_empty_body(self):
        source = JneSource()
        page = self._make_page("")
        result = source._parse_result(page, "12345678")
        assert result.dni == "12345678"
        assert result.nombre == ""
