"""Unit tests for Chile Registro Civil document validity source (SIDIV)."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.registro_civil import RegistroCivilResult
from openquery.sources.cl.registro_civil import RegistroCivilSource


class TestRegistroCivilResult:
    """Test RegistroCivilResult model."""

    def test_default_values(self):
        data = RegistroCivilResult()
        assert data.run == ""
        assert data.serial_number == ""
        assert data.document_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RegistroCivilResult(
            run="12345678-9",
            serial_number="A123456789",
            document_status="VIGENTE",
            details={"Estado": "VIGENTE"},
        )
        json_str = data.model_dump_json()
        restored = RegistroCivilResult.model_validate_json(json_str)
        assert restored.run == "12345678-9"
        assert restored.serial_number == "A123456789"
        assert restored.document_status == "VIGENTE"
        assert restored.details["Estado"] == "VIGENTE"

    def test_audit_excluded_from_json(self):
        data = RegistroCivilResult(run="12345678-9", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRegistroCivilSourceMeta:
    """Test RegistroCivilSource metadata."""

    def test_meta_name(self):
        source = RegistroCivilSource()
        assert source.meta().name == "cl.registro_civil"

    def test_meta_country(self):
        source = RegistroCivilSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = RegistroCivilSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = RegistroCivilSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = RegistroCivilSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RegistroCivilSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = RegistroCivilSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = RegistroCivilSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(
        self, body_text: str, table_rows: list[tuple[str, str]] | None = None
    ) -> MagicMock:
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

    def test_parse_vigente(self):
        source = RegistroCivilSource()
        page = self._make_page(
            "Consulta de Documentos\nRUN: 12.345.678-9\nEstado del Documento: VIGENTE\n"
        )
        result = source._parse_result(page, "12345678-9", "A123456789")
        assert result.run == "12345678-9"
        assert result.serial_number == "A123456789"
        assert result.document_status == "VIGENTE"

    def test_parse_no_vigente(self):
        source = RegistroCivilSource()
        page = self._make_page(
            "Consulta de Documentos\nEstado: NO VIGENTE\nEl documento se encuentra bloqueado.\n"
        )
        result = source._parse_result(page, "12345678-9", "A123456789")
        assert result.document_status == "NO VIGENTE"

    def test_parse_anulado(self):
        source = RegistroCivilSource()
        page = self._make_page("El documento ha sido anulado.")
        result = source._parse_result(page, "12345678-9", "B987654321")
        assert result.document_status == "NO VIGENTE"

    def test_parse_run_serial_preserved(self):
        source = RegistroCivilSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "99999999-9", "Z000000000")
        assert result.run == "99999999-9"
        assert result.serial_number == "Z000000000"

    def test_parse_from_table(self):
        source = RegistroCivilSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Estado del documento", "VIGENTE"),
                ("Tipo", "Cédula de Identidad"),
            ],
        )
        result = source._parse_result(page, "12345678-9", "A123456789")
        assert result.document_status == "VIGENTE"
        assert result.details["Estado del documento"] == "VIGENTE"

    def test_parse_vigente_case_insensitive(self):
        source = RegistroCivilSource()
        page = self._make_page("El documento está vigente según nuestros registros.")
        result = source._parse_result(page, "12345678-9", "A123456789")
        assert result.document_status == "VIGENTE"
