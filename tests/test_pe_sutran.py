"""Unit tests for pe.sutran — Peru SUTRAN traffic infraction record."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pe.sutran import SutranInfraction, SutranResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pe.sutran import SutranSource


class TestResult:
    def test_default_values(self):
        r = SutranResult()
        assert r.placa == ""
        assert r.total_infractions == 0
        assert r.infractions == []
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        r = SutranResult(placa="ABC123", audit={"evidence": "data"})
        json_str = r.model_dump_json()
        assert "audit" not in json_str
        assert r.audit == {"evidence": "data"}

    def test_model_roundtrip(self):
        r = SutranResult(
            placa="ABC123",
            total_infractions=2,
            infractions=[SutranInfraction(type="G01", date="2024-01-15", amount="200.00", status="Pendiente")],  # noqa: E501
        )
        r2 = SutranResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "ABC123"
        assert r2.total_infractions == 2
        assert len(r2.infractions) == 1
        assert r2.infractions[0].type == "G01"

    def test_infraction_default_values(self):
        inf = SutranInfraction()
        assert inf.type == ""
        assert inf.date == ""
        assert inf.amount == ""
        assert inf.status == ""


class TestSourceMeta:
    def test_meta_name(self):
        assert SutranSource().meta().name == "pe.sutran"

    def test_meta_country(self):
        assert SutranSource().meta().country == "PE"

    def test_meta_requires_browser(self):
        assert SutranSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert SutranSource().meta().requires_captcha is True

    def test_meta_supports_plate(self):
        assert DocumentType.PLATE in SutranSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        assert SutranSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SutranSource()._timeout == 30.0

    def test_custom_timeout(self):
        assert SutranSource(timeout=60.0)._timeout == 60.0


class TestParseResult:
    def _make_page(self, body_text: str, table_rows: list[tuple] | None = None) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        if table_rows:
            mock_rows = []
            for row_cells in table_rows:
                mock_row = MagicMock()
                mock_cells = []
                for text in row_cells:
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
        src = SutranSource()
        page = self._make_page("Sin infracciones")
        result = src._parse_result(page, "ABC123")
        assert result.placa == "ABC123"

    def test_parse_no_infractions(self):
        src = SutranSource()
        page = self._make_page("Sin infracciones encontradas")
        result = src._parse_result(page, "ABC123")
        assert result.total_infractions == 0
        assert result.infractions == []

    def test_parse_total_from_body(self):
        src = SutranSource()
        page = self._make_page("Total: 3 infracciones registradas")
        result = src._parse_result(page, "XYZ999")
        assert result.total_infractions == 3

    def test_parse_from_table_rows(self):
        src = SutranSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("G01", "2024-01-15", "200.00", "Pendiente"),
                ("L06", "2024-03-01", "150.00", "Pagado"),
            ],
        )
        result = src._parse_result(page, "ABC123")
        assert len(result.infractions) == 2
        assert result.total_infractions == 2
        assert result.infractions[0].type == "G01"
        assert result.infractions[0].amount == "200.00"
        assert result.infractions[1].status == "Pagado"

    def test_query_wrong_type_raises(self):
        src = SutranSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="12345"))

    def test_query_empty_plate_raises(self):
        src = SutranSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_query_calls_internal(self):
        from unittest.mock import patch

        src = SutranSource()
        mock_result = SutranResult(placa="ABC123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
            m.assert_called_once_with(placa="ABC123", audit=False)
