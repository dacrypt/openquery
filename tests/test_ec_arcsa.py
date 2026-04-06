"""Unit tests for Ecuador ARCSA health product registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.arcsa import ArcsaResult
from openquery.sources.ec.arcsa import ArcsaSource


class TestArcsaResult:
    """Test ArcsaResult model."""

    def test_default_values(self):
        data = ArcsaResult()
        assert data.search_term == ""
        assert data.product_name == ""
        assert data.registration_number == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ArcsaResult(
            search_term="ASPIRINA",
            product_name="ASPIRINA 500MG",
            registration_number="ARCSA-INS-0001234",
            status="VIGENTE",
            details={"Registro": "ARCSA-INS-0001234"},
        )
        json_str = data.model_dump_json()
        restored = ArcsaResult.model_validate_json(json_str)
        assert restored.search_term == "ASPIRINA"
        assert restored.product_name == "ASPIRINA 500MG"
        assert restored.registration_number == "ARCSA-INS-0001234"
        assert restored.status == "VIGENTE"

    def test_audit_excluded_from_json(self):
        data = ArcsaResult(search_term="ASPIRINA", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestArcsaSourceMeta:
    """Test ArcsaSource metadata."""

    def test_meta_name(self):
        source = ArcsaSource()
        assert source.meta().name == "ec.arcsa"

    def test_meta_country(self):
        source = ArcsaSource()
        assert source.meta().country == "EC"

    def test_meta_requires_browser(self):
        source = ArcsaSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = ArcsaSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = ArcsaSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ArcsaSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = ArcsaSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = ArcsaSource()
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
        source = ArcsaSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "ASPIRINA")
        assert result.search_term == "ASPIRINA"

    def test_parse_from_body_text(self):
        source = ArcsaSource()
        page = self._make_page(
            "Producto: ASPIRINA 500MG\nRegistro: ARCSA-INS-0001234\nEstado: VIGENTE\n"
        )
        result = source._parse_result(page, "ASPIRINA")
        assert result.product_name == "ASPIRINA 500MG"
        assert result.registration_number == "ARCSA-INS-0001234"
        assert result.status == "VIGENTE"

    def test_parse_from_table(self):
        source = ArcsaSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Nombre del Producto", "PARACETAMOL 1G"),
                ("Número de Registro", "ARCSA-INS-0009999"),
                ("Vigencia", "VIGENTE"),
            ],
        )
        result = source._parse_result(page, "PARACETAMOL")
        assert result.product_name == "PARACETAMOL 1G"
        assert result.registration_number == "ARCSA-INS-0009999"
        assert result.status == "VIGENTE"
        assert result.details["Nombre del Producto"] == "PARACETAMOL 1G"

    def test_parse_empty_body(self):
        source = ArcsaSource()
        page = self._make_page("")
        result = source._parse_result(page, "ASPIRINA")
        assert result.search_term == "ASPIRINA"
        assert result.product_name == ""
