"""Unit tests for Bolivia SEPREC company registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.bo.seprec import SeprecResult
from openquery.sources.bo.seprec import SeprecSource


class TestSeprecResult:
    """Test SeprecResult model."""

    def test_default_values(self):
        data = SeprecResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.nit == ""
        assert data.registration_status == ""
        assert data.folio == ""
        assert data.legal_representative == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SeprecResult(
            search_term="EMPRESA TEST",
            company_name="EMPRESA TEST S.R.L.",
            nit="1234567890",
            registration_status="ACTIVO",
            folio="12345",
            legal_representative="JUAN PEREZ",
            details={"actividad": "Comercio"},
        )
        json_str = data.model_dump_json()
        restored = SeprecResult.model_validate_json(json_str)
        assert restored.search_term == "EMPRESA TEST"
        assert restored.company_name == "EMPRESA TEST S.R.L."
        assert restored.nit == "1234567890"
        assert restored.registration_status == "ACTIVO"
        assert restored.folio == "12345"
        assert restored.legal_representative == "JUAN PEREZ"
        assert restored.details["actividad"] == "Comercio"

    def test_audit_excluded_from_json(self):
        data = SeprecResult(search_term="TEST", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}


class TestSeprecSourceMeta:
    """Test SeprecSource metadata."""

    def test_meta_name(self):
        source = SeprecSource()
        meta = source.meta()
        assert meta.name == "bo.seprec"

    def test_meta_country(self):
        source = SeprecSource()
        meta = source.meta()
        assert meta.country == "BO"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SeprecSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = SeprecSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = SeprecSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = SeprecSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = SeprecSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = SeprecSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_company_name(self):
        source = SeprecSource()
        page = self._make_page(
            "Resultados de búsqueda\nRazón Social: EMPRESA TEST S.R.L.\nEstado: ACTIVO\n"
        )
        result = source._parse_result(page, "EMPRESA TEST")
        assert result.search_term == "EMPRESA TEST"
        assert result.company_name == "EMPRESA TEST S.R.L."

    def test_parse_registration_status(self):
        source = SeprecSource()
        page = self._make_page("Razón Social: EMPRESA TEST S.R.L.\nEstado: ACTIVO\nFolio: 98765\n")
        result = source._parse_result(page, "EMPRESA TEST")
        assert result.registration_status == "ACTIVO"

    def test_parse_folio(self):
        source = SeprecSource()
        page = self._make_page(
            "Razón Social: EMPRESA TEST S.R.L.\nFolio: 98765\nRepresentante Legal: MARIA LOPEZ\n"
        )
        result = source._parse_result(page, "EMPRESA TEST")
        assert result.folio == "98765"

    def test_parse_legal_representative(self):
        source = SeprecSource()
        page = self._make_page(
            "Razón Social: EMPRESA TEST S.R.L.\nRepresentante Legal: MARIA LOPEZ\n"
        )
        result = source._parse_result(page, "EMPRESA TEST")
        assert result.legal_representative == "MARIA LOPEZ"

    def test_parse_nit(self):
        source = SeprecSource()
        page = self._make_page("NIT: 1234567890\nRazón Social: EMPRESA TEST S.R.L.\n")
        result = source._parse_result(page, "1234567890")
        assert result.nit == "1234567890"

    def test_parse_search_term_preserved(self):
        source = SeprecSource()
        page = self._make_page("No se encontraron resultados.")
        result = source._parse_result(page, "BUSQUEDA TEST")
        assert result.search_term == "BUSQUEDA TEST"

    def test_parse_empty_body(self):
        source = SeprecSource()
        page = self._make_page("")
        result = source._parse_result(page, "TEST")
        assert result.company_name == ""
        assert result.registration_status == ""
