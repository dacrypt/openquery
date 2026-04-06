"""Unit tests for Peru RENIEC identity consultation source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.reniec import ReniecResult
from openquery.sources.pe.reniec import ReniecSource


class TestReniecResult:
    """Test ReniecResult model."""

    def test_default_values(self):
        data = ReniecResult()
        assert data.dni == ""
        assert data.nombre == ""
        assert data.apellido_paterno == ""
        assert data.apellido_materno == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ReniecResult(
            dni="12345678",
            nombre="JUAN",
            apellido_paterno="GARCIA",
            apellido_materno="LOPEZ",
            details={"dni": "12345678"},
        )
        json_str = data.model_dump_json()
        restored = ReniecResult.model_validate_json(json_str)
        assert restored.dni == "12345678"
        assert restored.nombre == "JUAN"
        assert restored.apellido_paterno == "GARCIA"
        assert restored.apellido_materno == "LOPEZ"

    def test_audit_excluded_from_json(self):
        data = ReniecResult(dni="12345678", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestReniecSourceMeta:
    """Test ReniecSource metadata."""

    def test_meta_name(self):
        source = ReniecSource()
        assert source.meta().name == "pe.reniec"

    def test_meta_country(self):
        source = ReniecSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = ReniecSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = ReniecSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = ReniecSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ReniecSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = ReniecSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = ReniecSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


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

    def test_parse_from_body_text(self):
        source = ReniecSource()
        page = self._make_page(
            "Nombres: JUAN\n"
            "Apellido Paterno: GARCIA\n"
            "Apellido Materno: LOPEZ\n"
        )
        result = source._parse_result(page, "12345678")
        assert result.dni == "12345678"
        assert result.nombre == "JUAN"
        assert result.apellido_paterno == "GARCIA"
        assert result.apellido_materno == "LOPEZ"

    def test_parse_dni_preserved(self):
        source = ReniecSource()
        page = self._make_page("Sin resultados")
        result = source._parse_result(page, "99999999")
        assert result.dni == "99999999"

    def test_parse_from_table(self):
        source = ReniecSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("nombre", "MARIA"),
                ("apellido paterno", "TORRES"),
                ("apellido materno", "SILVA"),
            ],
        )
        result = source._parse_result(page, "12345678")
        assert result.nombre == "MARIA"
        assert result.apellido_paterno == "TORRES"
        assert result.apellido_materno == "SILVA"

    def test_parse_details_populated(self):
        source = ReniecSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("nombre", "ANA"),
                ("apellido paterno", "RIOS"),
            ],
        )
        result = source._parse_result(page, "12345678")
        assert "nombre" in result.details
        assert result.details["nombre"] == "ANA"
