"""Unit tests for br.susep — SUSEP insurance regulator."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.susep import SusepResult
from openquery.sources.br.susep import SusepSource


class TestSusepResult:
    def test_default_values(self):
        data = SusepResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.cnpj == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SusepResult(
            search_term="12345678000100",
            company_name="Seguradora Brasil S.A.",
            cnpj="12.345.678/0001-00",
            status="Autorizada",
        )
        restored = SusepResult.model_validate_json(data.model_dump_json())
        assert restored.company_name == "Seguradora Brasil S.A."
        assert restored.status == "Autorizada"

    def test_audit_excluded_from_json(self):
        data = SusepResult(search_term="123", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestSusepSourceMeta:
    def test_meta_name(self):
        assert SusepSource().meta().name == "br.susep"

    def test_meta_country(self):
        assert SusepSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        assert SusepSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert SusepSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert SusepSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_company_name(self):
        source = SusepSource()
        page = self._make_page("Razão Social: Seguradora Brasil S.A.\nCNPJ: 12.345.678/0001-00\nSituação: Autorizada\n")  # noqa: E501
        result = source._parse_result(page, "12345678000100")
        assert result.company_name == "Seguradora Brasil S.A."

    def test_parse_cnpj(self):
        source = SusepSource()
        page = self._make_page("Razão Social: ABC\nCNPJ: 12.345.678/0001-00\nSituação: Ativa\n")
        result = source._parse_result(page, "ABC")
        assert result.cnpj == "12.345.678/0001-00"

    def test_parse_status(self):
        source = SusepSource()
        page = self._make_page("Razão Social: ABC\nCNPJ: 00\nSituação: Cancelada\n")
        result = source._parse_result(page, "ABC")
        assert result.status == "Cancelada"
