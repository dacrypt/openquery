"""Unit tests for Chile PRT (vehicle technical inspection) source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.prt import PrtResult
from openquery.sources.cl.prt import PrtSource


class TestPrtResult:
    """Test PrtResult model."""

    def test_default_values(self):
        data = PrtResult()
        assert data.placa == ""
        assert data.rt_valid is None
        assert data.expiration_date == ""
        assert data.last_result == ""
        assert data.inspection_plant == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PrtResult(
            placa="ABCD12",
            rt_valid=True,
            expiration_date="31/12/2025",
            last_result="Aprobada",
            inspection_plant="Planta Central Santiago",
            details={"Resultado": "Aprobada"},
        )
        json_str = data.model_dump_json()
        restored = PrtResult.model_validate_json(json_str)
        assert restored.placa == "ABCD12"
        assert restored.rt_valid is True
        assert restored.expiration_date == "31/12/2025"
        assert restored.last_result == "Aprobada"
        assert restored.inspection_plant == "Planta Central Santiago"

    def test_round_trip_json_invalid(self):
        data = PrtResult(
            placa="XY1234",
            rt_valid=False,
            last_result="Rechazada",
        )
        json_str = data.model_dump_json()
        restored = PrtResult.model_validate_json(json_str)
        assert restored.rt_valid is False
        assert restored.last_result == "Rechazada"

    def test_audit_excluded_from_json(self):
        data = PrtResult(placa="ABCD12", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestPrtSourceMeta:
    """Test PrtSource metadata."""

    def test_meta_name(self):
        source = PrtSource()
        assert source.meta().name == "cl.prt"

    def test_meta_country(self):
        source = PrtSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = PrtSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = PrtSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = PrtSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = PrtSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = PrtSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = PrtSource()
        assert DocumentType.PLATE in source.meta().supported_inputs


class TestParseResult:
    """Test PrtSource._parse_result parsing logic with mocked page."""

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

    def test_parse_valid_rt(self):
        source = PrtSource()
        page = self._make_page(
            "Revision Tecnica Vehicular\n"
            "Patente: ABCD12\n"
            "Estado: Vigente\n"
            "Vencimiento: 31/12/2025\n"
            "Resultado: Aprobada\n"
            "Planta: Planta Norte Santiago\n"
        )
        result = source._parse_result(page, "ABCD12")
        assert result.placa == "ABCD12"
        assert result.rt_valid is True
        assert result.expiration_date == "31/12/2025"
        assert result.last_result == "Aprobada"
        assert result.inspection_plant == "Planta Norte Santiago"

    def test_parse_invalid_rt(self):
        source = PrtSource()
        page = self._make_page(
            "Revision Tecnica Vehicular\n"
            "Patente: XY1234\n"
            "Estado: Vencida\n"
            "Resultado: Rechazada\n"
        )
        result = source._parse_result(page, "XY1234")
        assert result.placa == "XY1234"
        assert result.rt_valid is False
        assert result.last_result == "Rechazada"

    def test_parse_expiration_date_formats(self):
        source = PrtSource()
        page = self._make_page("Vigencia: 2025-06-30\nEstado: Vigente\n")
        result = source._parse_result(page, "ABCD12")
        assert result.expiration_date == "2025-06-30"

    def test_parse_from_table(self):
        source = PrtSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Resultado", "Aprobada"),
                ("Planta", "Planta Central"),
                ("Vencimiento", "31/12/2025"),
            ],
        )
        result = source._parse_result(page, "ABCD12")
        assert result.last_result == "Aprobada"
        assert result.inspection_plant == "Planta Central"
        assert result.expiration_date == "31/12/2025"
        assert result.details["Resultado"] == "Aprobada"

    def test_parse_plate_preserved(self):
        source = PrtSource()
        page = self._make_page("Sin resultados para esta patente.")
        result = source._parse_result(page, "ZZZZ99")
        assert result.placa == "ZZZZ99"

    def test_parse_unknown_validity(self):
        source = PrtSource()
        page = self._make_page("Resultado indeterminado.")
        result = source._parse_result(page, "ABCD12")
        assert result.rt_valid is None
