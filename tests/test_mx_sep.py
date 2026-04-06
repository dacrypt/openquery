"""Unit tests for Mexico SEP professional certification source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.sep import SepResult
from openquery.sources.mx.sep import SepSource


class TestSepResult:
    """Test SepResult model."""

    def test_default_values(self):
        data = SepResult()
        assert data.nombre == ""
        assert data.cedula_number == ""
        assert data.institution == ""
        assert data.degree == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SepResult(
            nombre="JUAN PEREZ",
            cedula_number="1234567",
            institution="UNAM",
            degree="Licenciado en Derecho",
            details={"Cédula": "1234567"},
        )
        json_str = data.model_dump_json()
        restored = SepResult.model_validate_json(json_str)
        assert restored.nombre == "JUAN PEREZ"
        assert restored.cedula_number == "1234567"
        assert restored.institution == "UNAM"
        assert restored.degree == "Licenciado en Derecho"

    def test_audit_excluded_from_json(self):
        data = SepResult(nombre="JUAN PEREZ", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSepSourceMeta:
    """Test SepSource metadata."""

    def test_meta_name(self):
        source = SepSource()
        assert source.meta().name == "mx.sep"

    def test_meta_country(self):
        source = SepSource()
        assert source.meta().country == "MX"

    def test_meta_requires_browser(self):
        source = SepSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SepSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SepSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SepSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SepSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SepSource()
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

    def test_parse_nombre_preserved(self):
        source = SepSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "JUAN PEREZ")
        assert result.nombre == "JUAN PEREZ"

    def test_parse_from_body_text(self):
        source = SepSource()
        page = self._make_page(
            "Cédula: 1234567\nInstitución: UNAM\nCarrera: Licenciado en Derecho\n"
        )
        result = source._parse_result(page, "JUAN PEREZ")
        assert result.cedula_number == "1234567"
        assert result.institution == "UNAM"
        assert result.degree == "Licenciado en Derecho"

    def test_parse_from_table(self):
        source = SepSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Número de Cédula", "7654321"),
                ("Institución", "IPN"),
                ("Carrera", "Ingeniería Civil"),
            ],
        )
        result = source._parse_result(page, "ANA LOPEZ")
        assert result.cedula_number == "7654321"
        assert result.institution == "IPN"
        assert result.degree == "Ingeniería Civil"
        assert result.details["Institución"] == "IPN"

    def test_parse_empty_body(self):
        source = SepSource()
        page = self._make_page("")
        result = source._parse_result(page, "JUAN PEREZ")
        assert result.nombre == "JUAN PEREZ"
        assert result.cedula_number == ""
