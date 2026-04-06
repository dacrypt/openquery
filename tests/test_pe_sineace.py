"""Unit tests for Peru SINEACE educational accreditation source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pe.sineace import SineaceResult
from openquery.sources.pe.sineace import SineaceSource


class TestSineaceResult:
    """Test SineaceResult model."""

    def test_default_values(self):
        data = SineaceResult()
        assert data.search_term == ""
        assert data.institution_name == ""
        assert data.accreditation_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SineaceResult(
            search_term="PUCP",
            institution_name="Pontificia Universidad Católica del Perú",
            accreditation_status="ACREDITADA",
            details={"Estado": "ACREDITADA"},
        )
        json_str = data.model_dump_json()
        restored = SineaceResult.model_validate_json(json_str)
        assert restored.search_term == "PUCP"
        assert restored.institution_name == "Pontificia Universidad Católica del Perú"
        assert restored.accreditation_status == "ACREDITADA"

    def test_audit_excluded_from_json(self):
        data = SineaceResult(search_term="PUCP", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSineaceSourceMeta:
    """Test SineaceSource metadata."""

    def test_meta_name(self):
        source = SineaceSource()
        assert source.meta().name == "pe.sineace"

    def test_meta_country(self):
        source = SineaceSource()
        assert source.meta().country == "PE"

    def test_meta_requires_browser(self):
        source = SineaceSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SineaceSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SineaceSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SineaceSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SineaceSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SineaceSource()
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
        source = SineaceSource()
        page = self._make_page("Sin resultado")
        result = source._parse_result(page, "PUCP")
        assert result.search_term == "PUCP"

    def test_parse_from_body_text(self):
        source = SineaceSource()
        page = self._make_page(
            "Institución: Universidad Nacional Mayor de San Marcos\nEstado de Acreditación: ACREDITADA\n"  # noqa: E501
        )
        result = source._parse_result(page, "UNMSM")
        assert result.institution_name == "Universidad Nacional Mayor de San Marcos"
        assert result.accreditation_status == "ACREDITADA"

    def test_parse_from_table(self):
        source = SineaceSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("Institución", "UNMSM"),
                ("Acreditación", "ACREDITADA"),
            ],
        )
        result = source._parse_result(page, "UNMSM")
        assert result.institution_name == "UNMSM"
        assert result.accreditation_status == "ACREDITADA"
        assert result.details["Institución"] == "UNMSM"

    def test_parse_empty_body(self):
        source = SineaceSource()
        page = self._make_page("")
        result = source._parse_result(page, "PUCP")
        assert result.search_term == "PUCP"
        assert result.institution_name == ""
