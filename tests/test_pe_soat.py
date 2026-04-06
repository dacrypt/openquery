"""Unit tests for pe.soat — Peru SOAT mandatory vehicle insurance."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.pe.soat import SoatResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.pe.soat import SoatSource


class TestResult:
    def test_default_values(self):
        r = SoatResult()
        assert r.placa == ""
        assert r.soat_valid is False
        assert r.insurer == ""
        assert r.expiration_date == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        r = SoatResult(placa="ABC123", audit={"evidence": "data"})
        json_str = r.model_dump_json()
        assert "audit" not in json_str
        assert r.audit == {"evidence": "data"}

    def test_model_roundtrip(self):
        r = SoatResult(
            placa="ABC123",
            soat_valid=True,
            insurer="RIMAC SEGUROS",
            expiration_date="2025-06-30",
        )
        r2 = SoatResult.model_validate_json(r.model_dump_json())
        assert r2.placa == "ABC123"
        assert r2.soat_valid is True
        assert r2.insurer == "RIMAC SEGUROS"
        assert r2.expiration_date == "2025-06-30"


class TestSourceMeta:
    def test_meta_name(self):
        assert SoatSource().meta().name == "pe.soat"

    def test_meta_country(self):
        assert SoatSource().meta().country == "PE"

    def test_meta_requires_browser(self):
        assert SoatSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert SoatSource().meta().requires_captcha is True

    def test_meta_supports_plate(self):
        assert DocumentType.PLATE in SoatSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        assert SoatSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SoatSource()._timeout == 30.0

    def test_custom_timeout(self):
        assert SoatSource(timeout=60.0)._timeout == 60.0


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
        src = SoatSource()
        page = self._make_page("Sin resultado")
        result = src._parse_result(page, "ABC123")
        assert result.placa == "ABC123"

    def test_parse_insurer_from_body(self):
        src = SoatSource()
        page = self._make_page("Asegurador: RIMAC SEGUROS\nVencimiento: 2025-06-30\n")
        result = src._parse_result(page, "ABC123")
        assert result.insurer == "RIMAC SEGUROS"
        assert result.expiration_date == "2025-06-30"

    def test_parse_valid_from_body(self):
        src = SoatSource()
        page = self._make_page("Estado: VIGENTE\n")
        result = src._parse_result(page, "ABC123")
        assert result.soat_valid is True

    def test_parse_from_table(self):
        src = SoatSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Asegurador", "LA POSITIVA"),
                ("Vencimiento", "2025-12-31"),
                ("Estado", "VIGENTE"),
            ],
        )
        result = src._parse_result(page, "ABC123")
        assert result.insurer == "LA POSITIVA"
        assert result.expiration_date == "2025-12-31"
        assert result.soat_valid is True
        assert result.details["Asegurador"] == "LA POSITIVA"

    def test_parse_not_valid_when_no_keyword(self):
        src = SoatSource()
        page = self._make_page("No se encontro informacion")
        result = src._parse_result(page, "XYZ999")
        assert result.soat_valid is False

    def test_query_wrong_type_raises(self):
        src = SoatSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="12345"))

    def test_query_empty_plate_raises(self):
        src = SoatSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number=""))

    def test_query_calls_internal(self):
        from unittest.mock import patch

        src = SoatSource()
        mock_result = SoatResult(placa="ABC123")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.PLATE, document_number="ABC123"))
            m.assert_called_once_with(placa="ABC123", audit=False)
