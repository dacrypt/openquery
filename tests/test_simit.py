"""Unit tests for SIMIT source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.simit import SimitResult
from openquery.sources.co.simit import SimitSource


class TestSimitResult:
    """Test SimitResult model."""

    def test_default_values(self):
        data = SimitResult()
        assert data.comparendos == 0
        assert data.multas == 0
        assert data.acuerdos_pago == 0
        assert data.total_deuda == 0.0
        assert data.paz_y_salvo is False
        assert data.historial == []

    def test_round_trip_json(self):
        data = SimitResult(
            cedula="12345678",
            comparendos=0,
            multas=0,
            acuerdos_pago=0,
            total_deuda=0.0,
            paz_y_salvo=True,
            historial=[{"comparendo": "123", "estado": "Aplicado"}],
        )
        json_str = data.model_dump_json()
        restored = SimitResult.model_validate_json(json_str)
        assert restored.paz_y_salvo is True
        assert restored.cedula == "12345678"
        assert len(restored.historial) == 1

    def test_with_fines(self):
        data = SimitResult(
            cedula="12345678",
            comparendos=3,
            multas=2,
            acuerdos_pago=1,
            total_deuda=1500000.0,
            paz_y_salvo=False,
        )
        assert data.comparendos == 3
        assert data.multas == 2
        assert data.total_deuda == 1500000.0
        assert data.paz_y_salvo is False


class TestParseResults:
    """Test result parsing logic."""

    def test_parse_paz_y_salvo(self):
        source = SimitSource()

        mock_page = MagicMock()
        mock_page.query_selector.side_effect = lambda sel: (
            MagicMock() if "Paz y Salvo" in sel else None
        )
        mock_page.inner_text.return_value = (
            "Resumen\n"
            "Comparendos: 0\n"
            "Multas: 0\n"
            "Acuerdos de pago: 0\n"
            "Total: $ 0\n"
        )

        result = source._parse_results(mock_page, "12345678")

        assert result.paz_y_salvo is True
        assert result.comparendos == 0
        assert result.multas == 0
        assert result.total_deuda == 0.0

    def test_parse_with_fines(self):
        source = SimitSource()

        mock_page = MagicMock()
        mock_page.query_selector.return_value = None
        mock_page.inner_text.return_value = (
            "Resumen\n"
            "Comparendos: 3\n"
            "Multas: 2\n"
            "Acuerdos de pago: 1\n"
            "Total: $ 1.500.000\n"
        )

        result = source._parse_results(mock_page, "12345678")

        assert result.comparendos == 3
        assert result.multas == 2
        assert result.acuerdos_pago == 1
        assert result.total_deuda == 1500000.0
        assert result.paz_y_salvo is False


class TestParseHistorial:
    """Test historial parsing."""

    def test_no_historial_button(self):
        source = SimitSource()
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None

        result = source._parse_historial(mock_page)
        assert result == []

    def test_parse_historial_rows(self):
        source = SimitSource()

        mock_btn = MagicMock()
        mock_btn.inner_text.return_value = "Ver historial (2)"

        def make_cell(text):
            c = MagicMock()
            c.inner_text.return_value = text
            return c

        row1_cells = [
            make_cell("05001000000051651111"),
            make_cell("Medellin 05001000"),
            make_cell("11/03/2026"),
            make_cell("4777749"),
            make_cell("Medellin"),
            make_cell("CIA CIACON S.A.S."),
            make_cell("11/03/2026"),
            make_cell("Aplicado"),
        ]
        row2_cells = [
            make_cell("05088000000053773128"),
            make_cell("Bello 05088000"),
            make_cell("11/03/2026"),
            make_cell("4775948"),
            make_cell("Medellin"),
            make_cell("CIA CIACON S.A.S."),
            make_cell("11/03/2026"),
            make_cell("Aplicado"),
        ]

        mock_row1 = MagicMock()
        mock_row1.query_selector_all.return_value = row1_cells
        mock_row2 = MagicMock()
        mock_row2.query_selector_all.return_value = row2_cells

        mock_page = MagicMock()
        mock_page.query_selector.return_value = mock_btn
        mock_page.query_selector_all.return_value = [mock_row1, mock_row2]

        result = source._parse_historial(mock_page)
        assert len(result) == 2
        assert result[0]["comparendo"] == "05001000000051651111"
        assert result[0]["secretaria"] == "Medellin 05001000"
        assert result[0]["estado"] == "Aplicado"
        assert result[1]["comparendo"] == "05088000000053773128"


class TestSimitSourceInit:
    """Test source initialization."""

    def test_default_timeout(self):
        source = SimitSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SimitSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta(self):
        source = SimitSource()
        meta = source.meta()
        assert meta.name == "co.simit"
        assert meta.country == "CO"
        assert not meta.requires_captcha
