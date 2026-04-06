"""Unit tests for Peru SBS supervised financial entities source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.sbs import SbsResult
from openquery.sources.pe.sbs import SbsSource


class TestSbsResult:
    """Test SbsResult model."""

    def test_default_values(self):
        data = SbsResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.entity_type == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SbsResult(
            search_term="BCP",
            entity_name="BANCO DE CREDITO DEL PERU",
            entity_type="Banca Múltiple",
            status="AUTORIZADO",
            details={"Tipo": "Banca Múltiple"},
        )
        json_str = data.model_dump_json()
        restored = SbsResult.model_validate_json(json_str)
        assert restored.search_term == "BCP"
        assert restored.entity_name == "BANCO DE CREDITO DEL PERU"
        assert restored.entity_type == "Banca Múltiple"

    def test_audit_excluded_from_json(self):
        data = SbsResult(search_term="BCP", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSbsSourceMeta:
    """Test SbsSource metadata."""

    def test_meta_name(self):
        source = SbsSource()
        assert source.meta().name == "pe.sbs"

    def test_meta_country(self):
        source = SbsSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = SbsSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SbsSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SbsSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SbsSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SbsSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SbsSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str, table_rows: list[tuple] | None = None) -> MagicMock:
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

    def test_parse_search_term_preserved(self):
        source = SbsSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "BCP")
        assert result.search_term == "BCP"

    def test_parse_from_body_text(self):
        source = SbsSource()
        page = self._make_page(
            "Entidad: BANCO DE CREDITO DEL PERU\nTipo: Banca Múltiple\nEstado: AUTORIZADO\n"
        )
        result = source._parse_result(page, "BCP")
        assert result.entity_name == "BANCO DE CREDITO DEL PERU"
        assert result.entity_type == "Banca Múltiple"
        assert result.status == "AUTORIZADO"

    def test_parse_from_table(self):
        source = SbsSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Entidad", "RIMAC SEGUROS"),
                ("Tipo", "Empresa de Seguros"),
                ("Estado", "ACTIVO"),
            ],
        )
        result = source._parse_result(page, "RIMAC")
        assert result.entity_name == "RIMAC SEGUROS"
        assert result.entity_type == "Empresa de Seguros"
        assert result.status == "ACTIVO"
        assert result.details["Entidad"] == "RIMAC SEGUROS"

    def test_parse_empty_body(self):
        source = SbsSource()
        page = self._make_page("")
        result = source._parse_result(page, "BCP")
        assert result.search_term == "BCP"
        assert result.entity_name == ""
