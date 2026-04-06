"""Unit tests for Peru OSIPTEL telecom operators source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.osiptel import OsiptelResult
from openquery.sources.pe.osiptel import OsiptelSource


class TestOsiptelResult:
    """Test OsiptelResult model."""

    def test_default_values(self):
        data = OsiptelResult()
        assert data.search_term == ""
        assert data.operator_name == ""
        assert data.service_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OsiptelResult(
            search_term="CLARO",
            operator_name="AMERICA MOVIL PERU S.A.C.",
            service_type="Telefonía Móvil",
            details={"Servicio": "Telefonía Móvil"},
        )
        json_str = data.model_dump_json()
        restored = OsiptelResult.model_validate_json(json_str)
        assert restored.search_term == "CLARO"
        assert restored.operator_name == "AMERICA MOVIL PERU S.A.C."
        assert restored.service_type == "Telefonía Móvil"

    def test_audit_excluded_from_json(self):
        data = OsiptelResult(search_term="CLARO", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestOsiptelSourceMeta:
    """Test OsiptelSource metadata."""

    def test_meta_name(self):
        source = OsiptelSource()
        assert source.meta().name == "pe.osiptel"

    def test_meta_country(self):
        source = OsiptelSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = OsiptelSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = OsiptelSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = OsiptelSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = OsiptelSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = OsiptelSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = OsiptelSource()
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
        source = OsiptelSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "CLARO")
        assert result.search_term == "CLARO"

    def test_parse_from_body_text(self):
        source = OsiptelSource()
        page = self._make_page("Operador: AMERICA MOVIL PERU S.A.C.\nServicio: Telefonía Móvil\n")
        result = source._parse_result(page, "CLARO")
        assert result.operator_name == "AMERICA MOVIL PERU S.A.C."
        assert result.service_type == "Telefonía Móvil"

    def test_parse_from_table(self):
        source = OsiptelSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Operador", "TELEFONICA DEL PERU S.A.A."),
                ("Tipo de Servicio", "Internet Fijo"),
            ],
        )
        result = source._parse_result(page, "MOVISTAR")
        assert result.operator_name == "TELEFONICA DEL PERU S.A.A."
        assert result.service_type == "Internet Fijo"
        assert result.details["Operador"] == "TELEFONICA DEL PERU S.A.A."

    def test_parse_empty_body(self):
        source = OsiptelSource()
        page = self._make_page("")
        result = source._parse_result(page, "CLARO")
        assert result.search_term == "CLARO"
        assert result.operator_name == ""
