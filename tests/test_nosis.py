"""Unit tests for ar.nosis — Argentine credit report source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.nosis import NosisResult
from openquery.sources.ar.nosis import NosisSource


class TestNosisResult:
    """Test NosisResult model."""

    def test_default_values(self):
        data = NosisResult()
        assert data.cuit == ""
        assert data.company_name == ""
        assert data.credit_status == ""
        assert data.delinquency_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = NosisResult(
            cuit="20123456789",
            company_name="Empresa SA",
            credit_status="Normal",
            delinquency_status="Sin mora",
            details={"raw_text": "Normal sin deuda"},
        )
        json_str = data.model_dump_json()
        restored = NosisResult.model_validate_json(json_str)
        assert restored.cuit == "20123456789"
        assert restored.company_name == "Empresa SA"
        assert restored.credit_status == "Normal"
        assert restored.delinquency_status == "Sin mora"

    def test_audit_excluded_from_json(self):
        data = NosisResult(cuit="20123456789", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestNosisSourceMeta:
    """Test NosisSource metadata."""

    def test_meta_name(self):
        source = NosisSource()
        assert source.meta().name == "ar.nosis"

    def test_meta_country(self):
        source = NosisSource()
        assert source.meta().country == "AR"

    def test_meta_rate_limit(self):
        source = NosisSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = NosisSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = NosisSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = NosisSource()
        assert source._timeout == 30.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_company_name(self):
        source = NosisSource()
        page = self._make_page(
            "Informe NOSIS\n"
            "Razón social: Empresa SA\n"
            "Situación crediticia: Normal\n"
            "Sin mora registrada\n"
        )
        result = source._parse_result(page, "20123456789")
        assert result.cuit == "20123456789"
        assert result.company_name == "Empresa SA"
        assert result.credit_status == "Normal"
        assert result.delinquency_status == "Sin mora"

    def test_parse_delinquency(self):
        source = NosisSource()
        page = self._make_page("CUIT 20123456789\nPresenta mora en cuota 3\n")
        result = source._parse_result(page, "20123456789")
        assert result.delinquency_status == "Con mora"

    def test_parse_cuit_preserved(self):
        source = NosisSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "20987654321")
        assert result.cuit == "20987654321"

    def test_parse_details_present(self):
        source = NosisSource()
        page = self._make_page("Razón social: Test SA")
        result = source._parse_result(page, "20123456789")
        assert "raw_text" in result.details
