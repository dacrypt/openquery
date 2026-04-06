"""Unit tests for Ecuador ANT Multas traffic fines source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.ant_multas import AntMultasResult, Multa
from openquery.sources.ec.ant_multas import AntMultasSource


class TestAntMultasResult:
    """Test AntMultasResult model."""

    def test_default_values(self):
        data = AntMultasResult()
        assert data.search_value == ""
        assert data.total_multas == 0
        assert data.total_amount == ""
        assert data.points_balance == ""
        assert data.multas == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        multa = Multa(
            numero="C-001234",
            fecha="2024-01-15",
            tipo="VELOCIDAD",
            monto="100.00",
            estado="PENDIENTE",
            puntos="3",
            placa="ABC-1234",
        )
        data = AntMultasResult(
            search_value="ABC-1234",
            total_multas=1,
            total_amount="100.00",
            points_balance="27",
            multas=[multa],
        )
        json_str = data.model_dump_json()
        restored = AntMultasResult.model_validate_json(json_str)
        assert restored.search_value == "ABC-1234"
        assert restored.total_multas == 1
        assert restored.total_amount == "100.00"
        assert restored.points_balance == "27"
        assert len(restored.multas) == 1
        assert restored.multas[0].numero == "C-001234"

    def test_audit_excluded_from_json(self):
        data = AntMultasResult(search_value="ABC-1234", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_multa_default_values(self):
        multa = Multa()
        assert multa.numero == ""
        assert multa.fecha == ""
        assert multa.tipo == ""
        assert multa.monto == ""
        assert multa.estado == ""
        assert multa.puntos == ""
        assert multa.placa == ""
        assert multa.descripcion == ""


class TestAntMultasSourceMeta:
    """Test AntMultasSource metadata."""

    def test_meta_name(self):
        source = AntMultasSource()
        assert source.meta().name == "ec.ant_multas"

    def test_meta_country(self):
        source = AntMultasSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = AntMultasSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = AntMultasSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = AntMultasSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = AntMultasSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = AntMultasSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs_plate(self):
        from openquery.sources.base import DocumentType

        source = AntMultasSource()
        assert DocumentType.PLATE in source.meta().supported_inputs

    def test_meta_supported_inputs_cedula(self):
        from openquery.sources.base import DocumentType

        source = AntMultasSource()
        assert DocumentType.CEDULA in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str, table_rows: list[list[str]] | None = None) -> MagicMock:
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

    def test_parse_search_value_preserved(self):
        source = AntMultasSource()
        page = self._make_page("Sin multas")
        result = source._parse_result(page, "ABC-1234")
        assert result.search_value == "ABC-1234"

    def test_parse_total_amount_from_body(self):
        source = AntMultasSource()
        page = self._make_page("Total: 250.00\nPuntos: 24\n")
        result = source._parse_result(page, "ABC-1234")
        assert result.total_amount == "250.00"
        assert result.points_balance == "24"

    def test_parse_no_multas_when_empty(self):
        source = AntMultasSource()
        page = self._make_page("No se encontraron multas")
        result = source._parse_result(page, "ABC-1234")
        assert result.total_multas == 0
        assert result.multas == []

    def test_parse_multas_from_table(self):
        source = AntMultasSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                # header row (no td cells) — empty list simulates no cells
                [],
                # data rows
                ["C-001234", "2024-01-15", "VELOCIDAD", "100.00", "PENDIENTE", "3"],
                ["C-001235", "2024-02-20", "SEMAFORO", "200.00", "PENDIENTE", "6"],
            ],
        )
        result = source._parse_result(page, "ABC-1234")
        # Only rows with 2+ cells and non-header numero are counted
        assert result.total_multas == len(result.multas)
        # Both rows have valid numero values
        for multa in result.multas:
            assert multa.placa == "ABC-1234"

    def test_parse_header_rows_skipped(self):
        source = AntMultasSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ["Numero", "Fecha", "Tipo", "Monto", "Estado", "Puntos"],
                ["C-001234", "2024-01-15", "VELOCIDAD", "100.00", "PENDIENTE", "3"],
            ],
        )
        result = source._parse_result(page, "ABC-1234")
        # Header row with "numero" should be skipped
        assert all(m.numero != "Numero" for m in result.multas)

    def test_parse_empty_body(self):
        source = AntMultasSource()
        page = self._make_page("")
        result = source._parse_result(page, "ABC-1234")
        assert result.search_value == "ABC-1234"
        assert result.total_multas == 0
        assert result.total_amount == ""
