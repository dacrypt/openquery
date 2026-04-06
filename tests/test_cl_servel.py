"""Unit tests for Chile Servel electoral service source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.servel import ServelResult
from openquery.sources.cl.servel import ServelSource


class TestServelResult:
    """Test ServelResult model."""

    def test_default_values(self):
        data = ServelResult()
        assert data.rut == ""
        assert data.nombre == ""
        assert data.voting_location == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ServelResult(
            rut="12345678-9",
            nombre="MARIA SILVA",
            voting_location="LICEO A-10 SANTIAGO",
            details={"Local": "LICEO A-10"},
        )
        json_str = data.model_dump_json()
        restored = ServelResult.model_validate_json(json_str)
        assert restored.rut == "12345678-9"
        assert restored.nombre == "MARIA SILVA"
        assert restored.voting_location == "LICEO A-10 SANTIAGO"

    def test_audit_excluded_from_json(self):
        data = ServelResult(rut="12345678-9", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestServelSourceMeta:
    """Test ServelSource metadata."""

    def test_meta_name(self):
        source = ServelSource()
        assert source.meta().name == "cl.servel"

    def test_meta_country(self):
        source = ServelSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = ServelSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = ServelSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = ServelSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ServelSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = ServelSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = ServelSource()
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

    def test_parse_rut_preserved(self):
        source = ServelSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "12345678-9")
        assert result.rut == "12345678-9"

    def test_parse_from_body_text(self):
        source = ServelSource()
        page = self._make_page(
            "Nombre: MARIA SILVA\nLocal de Votación: LICEO A-10 SANTIAGO\n"
        )
        result = source._parse_result(page, "12345678-9")
        assert result.nombre == "MARIA SILVA"
        assert result.voting_location == "LICEO A-10 SANTIAGO"

    def test_parse_from_table(self):
        source = ServelSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Nombre", "PEDRO ROJAS"),
                ("Mesa de Votación", "ESCUELA VALPARAISO"),
            ],
        )
        result = source._parse_result(page, "98765432-1")
        assert result.nombre == "PEDRO ROJAS"
        assert result.voting_location == "ESCUELA VALPARAISO"
        assert result.details["Nombre"] == "PEDRO ROJAS"

    def test_parse_empty_body(self):
        source = ServelSource()
        page = self._make_page("")
        result = source._parse_result(page, "12345678-9")
        assert result.rut == "12345678-9"
        assert result.nombre == ""
