"""Unit tests for Chile Autopase (TAG highway toll debt) source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.autopase import AutopaseResult
from openquery.sources.cl.autopase import AutopaseSource


class TestAutopaseResult:
    """Test AutopaseResult model."""

    def test_default_values(self):
        data = AutopaseResult()
        assert data.placa == ""
        assert data.tag_status == ""
        assert data.debt_amount == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = AutopaseResult(
            placa="ABCD12",
            tag_status="Sin deuda",
            debt_amount="0",
            details={"Estado": "Sin deuda"},
        )
        json_str = data.model_dump_json()
        restored = AutopaseResult.model_validate_json(json_str)
        assert restored.placa == "ABCD12"
        assert restored.tag_status == "Sin deuda"
        assert restored.debt_amount == "0"

    def test_round_trip_json_with_debt(self):
        data = AutopaseResult(
            placa="XY1234",
            tag_status="Con deuda",
            debt_amount="15.500",
        )
        json_str = data.model_dump_json()
        restored = AutopaseResult.model_validate_json(json_str)
        assert restored.tag_status == "Con deuda"
        assert restored.debt_amount == "15.500"

    def test_audit_excluded_from_json(self):
        data = AutopaseResult(placa="ABCD12", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestAutopaseSourceMeta:
    """Test AutopaseSource metadata."""

    def test_meta_name(self):
        source = AutopaseSource()
        assert source.meta().name == "cl.autopase"

    def test_meta_country(self):
        source = AutopaseSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = AutopaseSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = AutopaseSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = AutopaseSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = AutopaseSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = AutopaseSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = AutopaseSource()
        assert DocumentType.PLATE in source.meta().supported_inputs


class TestParseResult:
    """Test AutopaseSource._parse_result parsing logic with mocked page."""

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

    def test_parse_no_debt(self):
        source = AutopaseSource()
        page = self._make_page(
            "Estado TAG Autopista\n"
            "Patente: ABCD12\n"
            "Estado: Sin deuda\n"
            "El vehiculo no registra deuda pendiente.\n"
        )
        result = source._parse_result(page, "ABCD12")
        assert result.placa == "ABCD12"
        assert result.tag_status == "Sin deuda"

    def test_parse_with_debt_amount(self):
        source = AutopaseSource()
        page = self._make_page(
            "Estado TAG Autopista\n"
            "Patente: XY1234\n"
            "Estado TAG: Con deuda\n"
            "Deuda: $15.500\n"
            "Monto: 15.500\n"
        )
        result = source._parse_result(page, "XY1234")
        assert result.placa == "XY1234"
        assert result.tag_status == "Con deuda"
        assert result.debt_amount == "15.500"

    def test_parse_status_inferred_no_debt(self):
        source = AutopaseSource()
        page = self._make_page("El TAG se encuentra al dia. Sin mora registrada.")
        result = source._parse_result(page, "ABCD12")
        assert result.tag_status == "Sin deuda"

    def test_parse_status_inferred_with_debt(self):
        source = AutopaseSource()
        page = self._make_page("Hay una deuda pendiente de pago en el sistema.")
        result = source._parse_result(page, "ABCD12")
        assert result.tag_status == "Con deuda"

    def test_parse_from_table(self):
        source = AutopaseSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Estado", "Sin deuda"),
                ("Saldo deudor", "0"),
            ],
        )
        result = source._parse_result(page, "ABCD12")
        assert result.tag_status == "Sin deuda"
        assert result.details["Estado"] == "Sin deuda"

    def test_parse_plate_preserved(self):
        source = AutopaseSource()
        page = self._make_page("Sin resultados para esta patente.")
        result = source._parse_result(page, "ZZZZ99")
        assert result.placa == "ZZZZ99"
