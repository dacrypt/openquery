"""Unit tests for Ecuador Registro Civil source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.registro_civil import RegistroCivilEcResult
from openquery.sources.ec.registro_civil import RegistroCivilEcSource


class TestRegistroCivilEcResult:
    """Test RegistroCivilEcResult model."""

    def test_default_values(self):
        data = RegistroCivilEcResult()
        assert data.cedula == ""
        assert data.nombre == ""
        assert data.civil_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroCivilEcResult(
            cedula="1234567890",
            nombre="JUAN CARLOS",
            civil_status="SOLTERO",
            details={"Estado Civil": "SOLTERO"},
        )
        json_str = data.model_dump_json()
        restored = RegistroCivilEcResult.model_validate_json(json_str)
        assert restored.cedula == "1234567890"
        assert restored.nombre == "JUAN CARLOS"
        assert restored.civil_status == "SOLTERO"

    def test_audit_excluded_from_json(self):
        data = RegistroCivilEcResult(cedula="1234567890", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroCivilEcSourceMeta:
    """Test RegistroCivilEcSource metadata."""

    def test_meta_name(self):
        source = RegistroCivilEcSource()
        assert source.meta().name == "ec.registro_civil"

    def test_meta_country(self):
        source = RegistroCivilEcSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = RegistroCivilEcSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = RegistroCivilEcSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = RegistroCivilEcSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroCivilEcSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = RegistroCivilEcSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = RegistroCivilEcSource()
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

    def test_parse_cedula_preserved(self):
        source = RegistroCivilEcSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "1234567890")
        assert result.cedula == "1234567890"

    def test_parse_nombre_from_body(self):
        source = RegistroCivilEcSource()
        page = self._make_page("Nombre: JUAN CARLOS PEREZ\nEstado Civil: SOLTERO\n")
        result = source._parse_result(page, "1234567890")
        assert result.nombre == "JUAN CARLOS PEREZ"
        assert result.civil_status == "SOLTERO"

    def test_parse_from_table(self):
        source = RegistroCivilEcSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Nombre", "MARIA ELENA"),
                ("Estado Civil", "CASADA"),
            ],
        )
        result = source._parse_result(page, "0987654321")
        assert result.nombre == "MARIA ELENA"
        assert result.civil_status == "CASADA"
        assert result.details["Nombre"] == "MARIA ELENA"

    def test_parse_empty_body(self):
        source = RegistroCivilEcSource()
        page = self._make_page("")
        result = source._parse_result(page, "1234567890")
        assert result.cedula == "1234567890"
        assert result.nombre == ""
