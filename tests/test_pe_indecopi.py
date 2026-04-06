"""Unit tests for Peru INDECOPI trademark/patent search source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.indecopi import IndecopiResult
from openquery.sources.pe.indecopi import IndecopiSource


class TestIndecopiResult:
    """Test IndecopiResult model."""

    def test_default_values(self):
        data = IndecopiResult()
        assert data.search_term == ""
        assert data.trademark_name == ""
        assert data.owner == ""
        assert data.status == ""
        assert data.registration_date == ""
        assert data.classes == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IndecopiResult(
            search_term="INCA COLA",
            trademark_name="INCA COLA",
            owner="COCA COLA PERU SAC",
            status="REGISTRADA",
            registration_date="01/01/2000",
            classes=["32", "33"],
        )
        json_str = data.model_dump_json()
        restored = IndecopiResult.model_validate_json(json_str)
        assert restored.search_term == "INCA COLA"
        assert restored.trademark_name == "INCA COLA"
        assert restored.owner == "COCA COLA PERU SAC"
        assert restored.status == "REGISTRADA"
        assert restored.classes == ["32", "33"]

    def test_audit_excluded_from_json(self):
        data = IndecopiResult(search_term="TEST", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestIndecopiSourceMeta:
    """Test IndecopiSource metadata."""

    def test_meta_name(self):
        source = IndecopiSource()
        assert source.meta().name == "pe.indecopi"

    def test_meta_country(self):
        source = IndecopiSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = IndecopiSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = IndecopiSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = IndecopiSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = IndecopiSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = IndecopiSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = IndecopiSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str, table_rows: list[tuple] | None = None) -> MagicMock:
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

    def test_parse_from_table(self):
        source = IndecopiSource()
        page = self._make_page(
            "Resultados",
            table_rows=[
                ("INCA COLA", "COCA COLA PERU SAC", "REGISTRADA", "01/01/2000", "32"),
            ],
        )
        result = source._parse_result(page, "INCA COLA")
        assert result.search_term == "INCA COLA"
        assert result.trademark_name == "INCA COLA"
        assert result.owner == "COCA COLA PERU SAC"
        assert result.status == "REGISTRADA"
        assert result.registration_date == "01/01/2000"
        assert "32" in result.classes

    def test_parse_from_body_text(self):
        source = IndecopiSource()
        page = self._make_page(
            "Marca: MARCA TEST\n"
            "Titular: EMPRESA TITULAR SAC\n"
            "Estado: REGISTRADA\n"
            "Fecha de Registro: 15/06/2010\n"
        )
        result = source._parse_result(page, "MARCA TEST")
        assert result.trademark_name == "MARCA TEST"
        assert result.owner == "EMPRESA TITULAR SAC"
        assert result.status == "REGISTRADA"
        assert result.registration_date == "15/06/2010"

    def test_parse_search_term_preserved(self):
        source = IndecopiSource()
        page = self._make_page("Sin resultados")
        result = source._parse_result(page, "MI MARCA")
        assert result.search_term == "MI MARCA"

    def test_parse_classes_split(self):
        source = IndecopiSource()
        page = self._make_page(
            "Resultados",
            table_rows=[
                ("MARCA XYZ", "TITULAR SA", "VIGENTE", "01/01/2015", "25, 35, 42"),
            ],
        )
        result = source._parse_result(page, "MARCA XYZ")
        assert "25" in result.classes
        assert "35" in result.classes
        assert "42" in result.classes
