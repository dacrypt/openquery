"""Unit tests for Chile CMF Fiscalizados source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.cmf_fiscalizados import CmfFiscalizadosResult
from openquery.sources.cl.cmf_fiscalizados import CmfFiscalizadosSource


class TestCmfFiscalizadosResult:
    """Test CmfFiscalizadosResult model."""

    def test_default_values(self):
        data = CmfFiscalizadosResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.rut == ""
        assert data.entity_type == ""
        assert data.authorization_status == ""
        assert data.address == ""
        assert data.branches == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CmfFiscalizadosResult(
            search_term="Banco de Chile",
            entity_name="Banco de Chile S.A.",
            rut="97.004.000-5",
            entity_type="Banco",
            authorization_status="Autorizado",
            address="Paseo Ahumada 251, Santiago",
            branches=["Sucursal Providencia", "Sucursal Las Condes"],
            details={"Tipo": "Banco", "Estado": "Autorizado"},
        )
        json_str = data.model_dump_json()
        restored = CmfFiscalizadosResult.model_validate_json(json_str)
        assert restored.search_term == "Banco de Chile"
        assert restored.entity_name == "Banco de Chile S.A."
        assert restored.rut == "97.004.000-5"
        assert restored.entity_type == "Banco"
        assert restored.authorization_status == "Autorizado"
        assert restored.branches == ["Sucursal Providencia", "Sucursal Las Condes"]

    def test_audit_excluded_from_json(self):
        data = CmfFiscalizadosResult(search_term="Banco", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCmfFiscalizadosSourceMeta:
    """Test CmfFiscalizadosSource metadata."""

    def test_meta_name(self):
        source = CmfFiscalizadosSource()
        assert source.meta().name == "cl.cmf_fiscalizados"

    def test_meta_country(self):
        source = CmfFiscalizadosSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = CmfFiscalizadosSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CmfFiscalizadosSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = CmfFiscalizadosSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CmfFiscalizadosSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CmfFiscalizadosSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = CmfFiscalizadosSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(
        self,
        body_text: str,
        table_rows: list[tuple[str, str]] | None = None,
    ) -> MagicMock:
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

    def test_parse_entity_name_from_text(self):
        source = CmfFiscalizadosSource()
        page = self._make_page(
            "Resultado de Entidad Fiscalizada\n"
            "Nombre de la Entidad: Banco de Chile S.A.\n"
            "RUT: 97.004.000-5\n"
            "Tipo de Entidad: Banco\n"
            "Autorización: Autorizado\n"
            "Dirección: Paseo Ahumada 251, Santiago\n"
        )
        result = source._parse_result(page, "Banco de Chile")
        assert result.search_term == "Banco de Chile"
        assert result.entity_name == "Banco de Chile S.A."
        assert result.rut == "97.004.000-5"
        assert result.entity_type == "Banco"
        assert result.authorization_status == "Autorizado"
        assert result.address == "Paseo Ahumada 251, Santiago"

    def test_parse_from_table(self):
        source = CmfFiscalizadosSource()
        page = self._make_page(
            "Entidad Fiscalizada",
            table_rows=[
                ("Nombre de la Entidad", "Compañía de Seguros XYZ"),
                ("RUT", "76.543.210-1"),
                ("Tipo de Entidad", "Compañía de Seguros"),
                ("Estado de Autorización", "Autorizado"),
                ("Dirección", "Av. Providencia 1234, Santiago"),
            ],
        )
        result = source._parse_result(page, "XYZ")
        assert result.entity_name == "Compañía de Seguros XYZ"
        assert result.rut == "76.543.210-1"
        assert result.entity_type == "Compañía de Seguros"
        assert result.authorization_status == "Autorizado"
        assert result.address == "Av. Providencia 1234, Santiago"
        assert result.details["Nombre de la Entidad"] == "Compañía de Seguros XYZ"

    def test_parse_branches(self):
        source = CmfFiscalizadosSource()
        page = self._make_page(
            "Entidad: ABC\n"
            "Sucursal: Providencia\n"
            "Sucursal: Las Condes\n"
            "Sucursal: Maipú\n"
        )
        result = source._parse_result(page, "ABC")
        assert len(result.branches) == 3
        assert "Providencia" in result.branches

    def test_parse_search_term_preserved(self):
        source = CmfFiscalizadosSource()
        page = self._make_page("Sin resultados")
        result = source._parse_result(page, "término de búsqueda")
        assert result.search_term == "término de búsqueda"

    def test_parse_empty_page(self):
        source = CmfFiscalizadosSource()
        page = self._make_page("")
        result = source._parse_result(page, "test")
        assert result.entity_name == ""
        assert result.rut == ""
        assert result.details == {}
        assert result.branches == []
