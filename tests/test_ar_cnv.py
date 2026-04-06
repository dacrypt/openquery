"""Unit tests for Argentina CNV securities regulator source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.cnv import CnvResult
from openquery.sources.ar.cnv import CnvSource


class TestCnvResult:
    """Test CnvResult model."""

    def test_default_values(self):
        data = CnvResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.registration_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CnvResult(
            search_term="GRUPO FINANCIERO",
            entity_name="GRUPO FINANCIERO SA",
            registration_status="REGISTRADA",
            details={"Estado": "REGISTRADA"},
        )
        json_str = data.model_dump_json()
        restored = CnvResult.model_validate_json(json_str)
        assert restored.search_term == "GRUPO FINANCIERO"
        assert restored.entity_name == "GRUPO FINANCIERO SA"
        assert restored.registration_status == "REGISTRADA"

    def test_audit_excluded_from_json(self):
        data = CnvResult(search_term="GRUPO FINANCIERO", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCnvSourceMeta:
    """Test CnvSource metadata."""

    def test_meta_name(self):
        source = CnvSource()
        assert source.meta().name == "ar.cnv"

    def test_meta_country(self):
        source = CnvSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = CnvSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CnvSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = CnvSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CnvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CnvSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CnvSource()
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
        source = CnvSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "GRUPO FINANCIERO")
        assert result.search_term == "GRUPO FINANCIERO"

    def test_parse_from_body_text(self):
        source = CnvSource()
        page = self._make_page(
            "Denominación: GRUPO FINANCIERO SA\nEstado: REGISTRADA\n"
        )
        result = source._parse_result(page, "GRUPO FINANCIERO")
        assert result.entity_name == "GRUPO FINANCIERO SA"
        assert result.registration_status == "REGISTRADA"

    def test_parse_from_table(self):
        source = CnvSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Razón Social", "INVERSIONES ABC SA"),
                ("Registro", "HABILITADO"),
            ],
        )
        result = source._parse_result(page, "INVERSIONES ABC")
        assert result.entity_name == "INVERSIONES ABC SA"
        assert result.registration_status == "HABILITADO"
        assert result.details["Razón Social"] == "INVERSIONES ABC SA"

    def test_parse_empty_body(self):
        source = CnvSource()
        page = self._make_page("")
        result = source._parse_result(page, "GRUPO FINANCIERO")
        assert result.search_term == "GRUPO FINANCIERO"
        assert result.entity_name == ""
