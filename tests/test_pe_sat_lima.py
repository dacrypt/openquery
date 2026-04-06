"""Unit tests for pe.sat_lima — Peru SAT Lima vehicle taxes and papeletas."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pe.sat_lima import SatLimaResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pe.sat_lima import SatLimaSource


class TestResult:
    def test_default_values(self):
        r = SatLimaResult()
        assert r.placa == ""
        assert r.total_papeletas == 0
        assert r.total_amount == ""
        assert r.tax_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        r = SatLimaResult(placa="ABC123", audit={"evidence": "data"})
        json_str = r.model_dump_json()
        assert "audit" not in json_str
        assert r.audit == {"evidence": "data"}

    def test_model_roundtrip(self):
        r = SatLimaResult(
            placa="ABC123",
            total_papeletas=3,
            total_amount="S/. 450.00",
            tax_status="Al Dia",
        )
        r2 = SatLimaResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "ABC123"
        assert r2.total_papeletas == 3
        assert r2.total_amount == "S/. 450.00"
        assert r2.tax_status == "Al Dia"


class TestSourceMeta:
    def test_meta_name(self):
        assert SatLimaSource().meta().name == "pe.sat_lima"

    def test_meta_country(self):
        assert SatLimaSource().meta().country == "PE"

    def test_meta_requires_browser(self):
        assert SatLimaSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert SatLimaSource().meta().requires_captcha is False

    def test_meta_supports_plate(self):
        assert DocumentType.PLATE in SatLimaSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        assert SatLimaSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SatLimaSource()._timeout == 30.0

    def test_custom_timeout(self):
        assert SatLimaSource(timeout=60.0)._timeout == 60.0


class TestParseResult:
    def _make_page(self, body_text: str, table_rows: list[tuple] | None = None) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        if table_rows:
            mock_rows = []
            for label, value in table_rows:
                mock_row = MagicMock()
                mock_cells = []
                for text in (label, value):
                    cell = MagicMock()
                    cell.inner_text.return_value = text
                    mock_cells.append(cell)
                mock_row.query_selector_all.return_value = mock_cells
                mock_rows.append(mock_row)
            page.query_selector_all.return_value = mock_rows
        else:
            page.query_selector_all.return_value = []
        return page

    def test_parse_placa_preserved(self):
        src = SatLimaSource()
        page = self._make_page("Sin resultado")
        result = src._parse_result(page, "ABC123")
        assert result.placa == "ABC123"

    def test_parse_amount_from_body(self):
        src = SatLimaSource()
        page = self._make_page("Total: S/. 450.00 pendiente\nImpuesto: Al Dia\n")
        result = src._parse_result(page, "ABC123")
        assert result.total_amount == "S/. 450.00"
        assert result.tax_status == "Al Dia"

    def test_parse_papeletas_count_from_body(self):
        src = SatLimaSource()
        page = self._make_page("Papeletas: 3 encontradas")
        result = src._parse_result(page, "ABC123")
        assert result.total_papeletas == 3

    def test_parse_from_table(self):
        src = SatLimaSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Monto Total", "S/. 300.00"),
                ("Tributo", "Pendiente"),
            ],
        )
        result = src._parse_result(page, "ABC123")
        assert result.details["Monto Total"] == "S/. 300.00"
        assert result.details["Tributo"] == "Pendiente"

    def test_parse_no_papeletas(self):
        src = SatLimaSource()
        page = self._make_page("No se encontraron papeletas pendientes")
        result = src._parse_result(page, "XYZ999")
        assert result.total_papeletas == 0
        assert result.total_amount == ""

    def test_query_wrong_type_raises(self):
        src = SatLimaSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="12345"))

    def test_query_empty_plate_raises(self):
        src = SatLimaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_query_calls_internal(self):
        from unittest.mock import patch

        src = SatLimaSource()
        mock_result = SatLimaResult(placa="ABC123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
            m.assert_called_once_with(placa="ABC123", audit=False)
