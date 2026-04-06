"""Unit tests for Chile Superintendencia de Pensiones AFP/AFC source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.spensiones import SpensionesResult
from openquery.sources.cl.spensiones import SpensionesSource


class TestSpensionesResult:
    """Test SpensionesResult model."""

    def test_default_values(self):
        data = SpensionesResult()
        assert data.rut == ""
        assert data.afp_name == ""
        assert data.afp_status == ""
        assert data.afc_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SpensionesResult(
            rut="12345678-9",
            afp_name="Habitat",
            afp_status="AFILIADO",
            afc_status="AFILIADO",
            details={"AFP": "Habitat", "Estado": "Activo"},
        )
        json_str = data.model_dump_json()
        restored = SpensionesResult.model_validate_json(json_str)
        assert restored.rut == "12345678-9"
        assert restored.afp_name == "Habitat"
        assert restored.afp_status == "AFILIADO"
        assert restored.afc_status == "AFILIADO"

    def test_audit_excluded_from_json(self):
        data = SpensionesResult(rut="12345678-9", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSpensionesSourceMeta:
    """Test SpensionesSource metadata."""

    def test_meta_name(self):
        source = SpensionesSource()
        assert source.meta().name == "cl.spensiones"

    def test_meta_country(self):
        source = SpensionesSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = SpensionesSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = SpensionesSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SpensionesSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = SpensionesSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SpensionesSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = SpensionesSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str, table_rows: list[tuple[str, str]] | None = None) -> MagicMock:
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

    def test_parse_afiliado_afp(self):
        source = SpensionesSource()
        page = self._make_page(
            "Resultado de consulta\n"
            "AFP: Habitat\n"
            "Estado de Afiliación: AFILIADO\n"
            "AFC: AFILIADO\n"
        )
        result = source._parse_result(page, "12345678-9")
        assert result.rut == "12345678-9"
        assert result.afp_name == "Habitat"
        assert result.afp_status == "AFILIADO"
        assert result.afc_status == "AFILIADO"

    def test_parse_no_afiliado(self):
        source = SpensionesSource()
        page = self._make_page("No se encontró afiliación. No afiliado a ninguna AFP.")
        result = source._parse_result(page, "99999999-9")
        assert result.rut == "99999999-9"
        assert result.afp_status == "NO AFILIADO"

    def test_parse_rut_preserved(self):
        source = SpensionesSource()
        page = self._make_page("Sin resultados")
        result = source._parse_result(page, "11111111-1")
        assert result.rut == "11111111-1"

    def test_parse_from_table(self):
        source = SpensionesSource()
        page = self._make_page(
            "Resultado",
            table_rows=[
                ("AFP", "Capital"),
                ("Estado de Afiliación AFP", "AFILIADO"),
                ("AFC", "AFILIADO"),
            ],
        )
        result = source._parse_result(page, "12345678-9")
        assert result.afp_name == "Capital"
        assert result.afp_status == "AFILIADO"
        assert result.afc_status == "AFILIADO"
        assert result.details["AFP"] == "Capital"
