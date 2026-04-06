"""Unit tests for pe.citv — Peru MTC vehicle technical inspection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pe.citv import CitvResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pe.citv import CitvSource


class TestResult:
    def test_default_values(self):
        r = CitvResult()
        assert r.placa == ""
        assert r.citv_valid is False
        assert r.expiration_date == ""
        assert r.inspection_center == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        r = CitvResult(placa="ABC123", audit={"evidence": "data"})
        json_str = r.model_dump_json()
        assert "audit" not in json_str
        assert r.audit == {"evidence": "data"}

    def test_model_roundtrip(self):
        r = CitvResult(
            placa="ABC123",
            citv_valid=True,
            expiration_date="2025-09-30",
            inspection_center="CETRUM SAC",
        )
        r2 = CitvResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "ABC123"
        assert r2.citv_valid is True
        assert r2.expiration_date == "2025-09-30"
        assert r2.inspection_center == "CETRUM SAC"


class TestSourceMeta:
    def test_meta_name(self):
        assert CitvSource().meta().name == "pe.citv"

    def test_meta_country(self):
        assert CitvSource().meta().country == "PE"

    def test_meta_requires_browser(self):
        assert CitvSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert CitvSource().meta().requires_captcha is True

    def test_meta_supports_plate(self):
        assert DocumentType.PLATE in CitvSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        assert CitvSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert CitvSource()._timeout == 30.0

    def test_custom_timeout(self):
        assert CitvSource(timeout=60.0)._timeout == 60.0


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
        src = CitvSource()
        page = self._make_page("Sin resultado")
        result = src._parse_result(page, "ABC123")
        assert result.placa == "ABC123"

    def test_parse_center_from_body(self):
        src = CitvSource()
        page = self._make_page("Centro: CETRUM SAC\nVencimiento: 2025-09-30\n")
        result = src._parse_result(page, "ABC123")
        assert result.inspection_center == "CETRUM SAC"
        assert result.expiration_date == "2025-09-30"

    def test_parse_valid_from_body(self):
        src = CitvSource()
        page = self._make_page("Estado: APROBADO\n")
        result = src._parse_result(page, "ABC123")
        assert result.citv_valid is True

    def test_parse_from_table(self):
        src = CitvSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Centro", "INSPECCION TECNICA PERU"),
                ("Vencimiento", "2025-06-15"),
                ("Estado", "APROBADO"),
            ],
        )
        result = src._parse_result(page, "ABC123")
        assert result.inspection_center == "INSPECCION TECNICA PERU"
        assert result.expiration_date == "2025-06-15"
        assert result.citv_valid is True
        assert result.details["Centro"] == "INSPECCION TECNICA PERU"

    def test_parse_not_valid_when_no_keyword(self):
        src = CitvSource()
        page = self._make_page("No se encontro informacion")
        result = src._parse_result(page, "XYZ999")
        assert result.citv_valid is False

    def test_query_wrong_type_raises(self):
        src = CitvSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="12345"))

    def test_query_empty_plate_raises(self):
        src = CitvSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_query_calls_internal(self):
        from unittest.mock import patch

        src = CitvSource()
        mock_result = CitvResult(placa="ABC123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
            m.assert_called_once_with(placa="ABC123", audit=False)
