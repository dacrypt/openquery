"""Unit tests for Mexico CNBV banking supervisor source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.cnbv import CnbvResult
from openquery.sources.mx.cnbv import CnbvSource


class TestCnbvResult:
    """Test CnbvResult model."""

    def test_default_values(self):
        data = CnbvResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.entity_type == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CnbvResult(
            search_term="BANAMEX",
            entity_name="CITIBANAMEX SA",
            entity_type="Banco Múltiple",
            status="AUTORIZADA",
            details={"Tipo": "Banco Múltiple"},
        )
        json_str = data.model_dump_json()
        restored = CnbvResult.model_validate_json(json_str)
        assert restored.search_term == "BANAMEX"
        assert restored.entity_name == "CITIBANAMEX SA"
        assert restored.entity_type == "Banco Múltiple"
        assert restored.status == "AUTORIZADA"

    def test_audit_excluded_from_json(self):
        data = CnbvResult(search_term="BANAMEX", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCnbvSourceMeta:
    """Test CnbvSource metadata."""

    def test_meta_name(self):
        source = CnbvSource()
        assert source.meta().name == "mx.cnbv"

    def test_meta_country(self):
        source = CnbvSource()
        assert source.meta().country == "MX"

    def test_meta_requires_browser(self):
        source = CnbvSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CnbvSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = CnbvSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CnbvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CnbvSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CnbvSource()
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
        source = CnbvSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "BANAMEX")
        assert result.search_term == "BANAMEX"

    def test_parse_from_body_text(self):
        source = CnbvSource()
        page = self._make_page(
            "Entidad: CITIBANAMEX SA\nTipo: Banco Múltiple\nEstado: AUTORIZADA\n"
        )
        result = source._parse_result(page, "BANAMEX")
        assert result.entity_name == "CITIBANAMEX SA"
        assert result.entity_type == "Banco Múltiple"
        assert result.status == "AUTORIZADA"

    def test_parse_from_table(self):
        source = CnbvSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Nombre de Entidad", "BBVA MEXICO SA"),
                ("Tipo", "Banco Múltiple"),
                ("Estatus", "AUTORIZADA"),
            ],
        )
        result = source._parse_result(page, "BBVA")
        assert result.entity_name == "BBVA MEXICO SA"
        assert result.entity_type == "Banco Múltiple"
        assert result.status == "AUTORIZADA"
        assert result.details["Nombre de Entidad"] == "BBVA MEXICO SA"

    def test_parse_empty_body(self):
        source = CnbvSource()
        page = self._make_page("")
        result = source._parse_result(page, "BANAMEX")
        assert result.search_term == "BANAMEX"
        assert result.entity_name == ""
