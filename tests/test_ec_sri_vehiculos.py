"""Unit tests for Ecuador SRI Vehiculos vehicle tax source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.sri_vehiculos import SriVehiculosResult
from openquery.sources.ec.sri_vehiculos import SriVehiculosSource


class TestSriVehiculosResult:
    """Test SriVehiculosResult model."""

    def test_default_values(self):
        data = SriVehiculosResult()
        assert data.placa == ""
        assert data.vehicle_description == ""
        assert data.brand == ""
        assert data.model == ""
        assert data.year == ""
        assert data.impuesto_vehicular == ""
        assert data.sppat_amount == ""
        assert data.total_due == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SriVehiculosResult(
            placa="ABC-1234",
            brand="CHEVROLET",
            model="AVEO",
            year="2018",
            impuesto_vehicular="120.50",
            sppat_amount="45.00",
            total_due="165.50",
            registration_status="AL DIA",
        )
        json_str = data.model_dump_json()
        restored = SriVehiculosResult.model_validate_json(json_str)
        assert restored.placa == "ABC-1234"
        assert restored.brand == "CHEVROLET"
        assert restored.model == "AVEO"
        assert restored.year == "2018"
        assert restored.impuesto_vehicular == "120.50"
        assert restored.sppat_amount == "45.00"
        assert restored.total_due == "165.50"

    def test_audit_excluded_from_json(self):
        data = SriVehiculosResult(placa="ABC-1234", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSriVehiculosSourceMeta:
    """Test SriVehiculosSource metadata."""

    def test_meta_name(self):
        source = SriVehiculosSource()
        assert source.meta().name == "ec.sri_vehiculos"

    def test_meta_country(self):
        source = SriVehiculosSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = SriVehiculosSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SriVehiculosSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SriVehiculosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SriVehiculosSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SriVehiculosSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SriVehiculosSource()
        assert DocumentType.PLATE in source.meta().supported_inputs

    def test_meta_only_plate_supported(self):
        from openquery.sources.base import DocumentType

        source = SriVehiculosSource()
        assert DocumentType.CEDULA not in source.meta().supported_inputs


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

    def test_parse_placa_preserved(self):
        source = SriVehiculosSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "ABC-1234")
        assert result.placa == "ABC-1234"

    def test_parse_brand_from_body(self):
        source = SriVehiculosSource()
        page = self._make_page("Marca: CHEVROLET\nModelo: AVEO\nAño: 2018\n")
        result = source._parse_result(page, "ABC-1234")
        assert result.brand == "CHEVROLET"
        assert result.model == "AVEO"
        assert result.year == "2018"

    def test_parse_tax_amounts(self):
        source = SriVehiculosSource()
        page = self._make_page(
            "Impuesto Vehicular: 120.50\nSPPAT: 45.00\nTotal: 165.50\n"
        )
        result = source._parse_result(page, "ABC-1234")
        assert result.impuesto_vehicular == "120.50"
        assert result.sppat_amount == "45.00"
        assert result.total_due == "165.50"

    def test_parse_registration_status(self):
        source = SriVehiculosSource()
        page = self._make_page("Estado: AL DIA\n")
        result = source._parse_result(page, "ABC-1234")
        assert result.registration_status == "AL DIA"

    def test_parse_table_rows(self):
        source = SriVehiculosSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Marca", "TOYOTA"),
                ("Modelo", "HILUX"),
                ("Año", "2020"),
                ("SPPAT", "50.00"),
                ("Total", "200.00"),
            ],
        )
        result = source._parse_result(page, "XYZ-9999")
        assert result.brand == "TOYOTA"
        assert result.model == "HILUX"
        assert result.year == "2020"
        assert result.sppat_amount == "50.00"
        assert result.total_due == "200.00"

    def test_parse_empty_body(self):
        source = SriVehiculosSource()
        page = self._make_page("")
        result = source._parse_result(page, "ABC-1234")
        assert result.placa == "ABC-1234"
        assert result.brand == ""
        assert result.total_due == ""
