"""Unit tests for Chile SII Deuda (tax situation of third parties) source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.sii_deuda import SiiDeudaResult
from openquery.sources.cl.sii_deuda import SiiDeudaSource


class TestSiiDeudaResult:
    """Test SiiDeudaResult model."""

    def test_default_values(self):
        data = SiiDeudaResult()
        assert data.rut == ""
        assert data.tax_status == ""
        assert data.has_debt is None
        assert data.debt_indicators == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SiiDeudaResult(
            rut="12345678-9",
            tax_status="Al día",
            has_debt=False,
            debt_indicators=[],
            details={"Situación Tributaria": "Al día"},
        )
        json_str = data.model_dump_json()
        restored = SiiDeudaResult.model_validate_json(json_str)
        assert restored.rut == "12345678-9"
        assert restored.tax_status == "Al día"
        assert restored.has_debt is False
        assert restored.debt_indicators == []

    def test_round_trip_json_with_debt(self):
        data = SiiDeudaResult(
            rut="98765432-1",
            tax_status="Con deuda",
            has_debt=True,
            debt_indicators=["Deuda IVA pendiente", "F29 no presentado"],
        )
        json_str = data.model_dump_json()
        restored = SiiDeudaResult.model_validate_json(json_str)
        assert restored.has_debt is True
        assert len(restored.debt_indicators) == 2

    def test_audit_excluded_from_json(self):
        data = SiiDeudaResult(rut="12345678-9", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSiiDeudaSourceMeta:
    """Test SiiDeudaSource metadata."""

    def test_meta_name(self):
        source = SiiDeudaSource()
        assert source.meta().name == "cl.sii_deuda"

    def test_meta_country(self):
        source = SiiDeudaSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = SiiDeudaSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SiiDeudaSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SiiDeudaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SiiDeudaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SiiDeudaSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SiiDeudaSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

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
        source = SiiDeudaSource()
        page = self._make_page(
            "Situación Tributaria de Terceros\n"
            "RUT: 12345678-9\n"
            "Situación Tributaria: Al día\n"
            "Sin deuda registrada en el sistema.\n"
        )
        result = source._parse_result(page, "12345678-9")
        assert result.rut == "12345678-9"
        assert result.has_debt is False

    def test_parse_with_debt(self):
        source = SiiDeudaSource()
        page = self._make_page(
            "Situación Tributaria de Terceros\n"
            "RUT: 98765432-1\n"
            "Estado: Con deuda\n"
            "El contribuyente adeuda impuestos pendientes.\n"
            "Indicador: Deuda IVA sin pagar\n"
        )
        result = source._parse_result(page, "98765432-1")
        assert result.rut == "98765432-1"
        assert result.has_debt is True
        assert len(result.debt_indicators) >= 1
        assert result.debt_indicators[0] == "Deuda IVA sin pagar"

    def test_parse_tax_status_from_text(self):
        source = SiiDeudaSource()
        page = self._make_page(
            "Situación tributaria: Contribuyente activo al día\n"
        )
        result = source._parse_result(page, "12345678-9")
        assert result.tax_status == "Contribuyente activo al día"

    def test_parse_from_table(self):
        source = SiiDeudaSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Situación Tributaria", "Al día"),
                ("Última Declaración", "Presentada"),
            ],
        )
        result = source._parse_result(page, "12345678-9")
        assert result.tax_status == "Al día"
        assert result.details["Situación Tributaria"] == "Al día"
        assert result.details["Última Declaración"] == "Presentada"

    def test_parse_rut_preserved(self):
        source = SiiDeudaSource()
        page = self._make_page("Sin resultados para este RUT.")
        result = source._parse_result(page, "99999999-9")
        assert result.rut == "99999999-9"

    def test_parse_unknown_debt_status(self):
        source = SiiDeudaSource()
        page = self._make_page("Resultado indeterminado.")
        result = source._parse_result(page, "12345678-9")
        assert result.has_debt is None
