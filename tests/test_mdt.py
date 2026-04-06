"""Unit tests for Ecuador MDT Ministerio del Trabajo labor consultation source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ec.mdt import MdtResult
from openquery.sources.ec.mdt import MdtSource


class TestMdtResult:
    """Test MdtResult model."""

    def test_default_values(self):
        data = MdtResult()
        assert data.search_value == ""
        assert data.employer_name == ""
        assert data.labor_status == ""
        assert data.contract_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = MdtResult(
            search_value="1234567890",
            employer_name="EMPRESA ABC S.A.",
            labor_status="ACTIVO",
            contract_type="INDEFINIDO",
            details={"sector": "PRIVADO"},
        )
        json_str = data.model_dump_json()
        restored = MdtResult.model_validate_json(json_str)
        assert restored.search_value == "1234567890"
        assert restored.employer_name == "EMPRESA ABC S.A."
        assert restored.labor_status == "ACTIVO"
        assert restored.contract_type == "INDEFINIDO"
        assert restored.details["sector"] == "PRIVADO"

    def test_audit_excluded_from_json(self):
        data = MdtResult(search_value="1234567890", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}


class TestMdtSourceMeta:
    """Test MdtSource metadata."""

    def test_meta_name(self):
        source = MdtSource()
        meta = source.meta()
        assert meta.name == "ec.mdt"

    def test_meta_country(self):
        source = MdtSource()
        meta = source.meta()
        assert meta.country == "EC"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = MdtSource()
        meta = source.meta()
        assert DocumentType.CEDULA in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = MdtSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = MdtSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = MdtSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = MdtSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = MdtSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_employer_name(self):
        source = MdtSource()
        page = self._make_page(
            "Consulta Laboral\n"
            "Empleador: EMPRESA ABC S.A.\n"
            "Estado: ACTIVO\n"
        )
        result = source._parse_result(page, "1234567890")
        assert result.search_value == "1234567890"
        assert result.employer_name == "EMPRESA ABC S.A."

    def test_parse_labor_status(self):
        source = MdtSource()
        page = self._make_page(
            "Empleador: EMPRESA XYZ\n"
            "Estado: ACTIVO\n"
            "Contrato: INDEFINIDO\n"
        )
        result = source._parse_result(page, "1234567890")
        assert result.labor_status == "ACTIVO"

    def test_parse_contract_type(self):
        source = MdtSource()
        page = self._make_page(
            "Empleador: EMPRESA XYZ\n"
            "Contrato: PLAZO FIJO\n"
        )
        result = source._parse_result(page, "1234567890")
        assert result.contract_type == "PLAZO FIJO"

    def test_parse_details(self):
        source = MdtSource()
        page = self._make_page(
            "Empleador: EMPRESA XYZ\n"
            "Cargo: ANALISTA\n"
            "Salario: 500.00\n"
        )
        result = source._parse_result(page, "1234567890")
        assert "Cargo" in result.details
        assert result.details["Cargo"] == "ANALISTA"

    def test_parse_search_value_preserved(self):
        source = MdtSource()
        page = self._make_page("No se encontraron resultados.")
        result = source._parse_result(page, "9999999999")
        assert result.search_value == "9999999999"

    def test_parse_empty_body(self):
        source = MdtSource()
        page = self._make_page("")
        result = source._parse_result(page, "1234567890")
        assert result.employer_name == ""
        assert result.labor_status == ""
