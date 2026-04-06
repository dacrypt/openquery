"""Unit tests for Chile SII Tasacion (vehicle tax valuation) source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.sii_tasacion import SiiTasacionResult
from openquery.sources.cl.sii_tasacion import SiiTasacionSource


class TestSiiTasacionResult:
    """Test SiiTasacionResult model."""

    def test_default_values(self):
        data = SiiTasacionResult()
        assert data.placa == ""
        assert data.tasacion_value == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SiiTasacionResult(
            placa="ABCD12",
            tasacion_value="8.500.000",
            vehicle_description="Toyota Yaris 2020",
            details={"Tasacion": "8.500.000"},
        )
        json_str = data.model_dump_json()
        restored = SiiTasacionResult.model_validate_json(json_str)
        assert restored.placa == "ABCD12"
        assert restored.tasacion_value == "8.500.000"
        assert restored.vehicle_description == "Toyota Yaris 2020"

    def test_round_trip_json_no_value(self):
        data = SiiTasacionResult(placa="XY1234")
        json_str = data.model_dump_json()
        restored = SiiTasacionResult.model_validate_json(json_str)
        assert restored.placa == "XY1234"
        assert restored.tasacion_value == ""

    def test_audit_excluded_from_json(self):
        data = SiiTasacionResult(placa="ABCD12", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSiiTasacionSourceMeta:
    """Test SiiTasacionSource metadata."""

    def test_meta_name(self):
        source = SiiTasacionSource()
        assert source.meta().name == "cl.sii_tasacion"

    def test_meta_country(self):
        source = SiiTasacionSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = SiiTasacionSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SiiTasacionSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SiiTasacionSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SiiTasacionSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SiiTasacionSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SiiTasacionSource()
        assert DocumentType.PLATE in source.meta().supported_inputs


class TestParseResult:
    """Test SiiTasacionSource._parse_result parsing logic with mocked page."""

    def _make_page(
        self,
        body_text: str,
        table_rows: list[tuple[str, str]] | None = None,
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

    def test_parse_tasacion_value(self):
        source = SiiTasacionSource()
        page = self._make_page(
            "Tasacion Fiscal Vehicular\n"
            "Patente: ABCD12\n"
            "Tasacion: $8.500.000\n"
            "Descripcion: Toyota Yaris 2020\n"
        )
        result = source._parse_result(page, "ABCD12")
        assert result.placa == "ABCD12"
        assert result.tasacion_value == "8.500.000"
        assert result.vehicle_description == "Toyota Yaris 2020"

    def test_parse_valor_fiscal(self):
        source = SiiTasacionSource()
        page = self._make_page(
            "Valor Fiscal: 12.000.000\n"
            "Marca: Chevrolet\n"
        )
        result = source._parse_result(page, "XY1234")
        assert result.tasacion_value == "12.000.000"
        assert result.vehicle_description == "Chevrolet"

    def test_parse_from_table(self):
        source = SiiTasacionSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Tasacion Fiscal", "8.500.000"),
                ("Marca", "Toyota"),
                ("Modelo", "Yaris"),
            ],
        )
        result = source._parse_result(page, "ABCD12")
        assert result.tasacion_value == "8.500.000"
        assert result.vehicle_description == "Toyota"
        assert result.details["Tasacion Fiscal"] == "8.500.000"

    def test_parse_plate_preserved(self):
        source = SiiTasacionSource()
        page = self._make_page("Sin resultados para esta patente.")
        result = source._parse_result(page, "ZZZZ99")
        assert result.placa == "ZZZZ99"

    def test_parse_empty_page(self):
        source = SiiTasacionSource()
        page = self._make_page("")
        result = source._parse_result(page, "ABCD12")
        assert result.tasacion_value == ""
        assert result.vehicle_description == ""
        assert result.details == {}
