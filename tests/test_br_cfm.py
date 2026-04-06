"""Unit tests for br.cfm — CFM doctor registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.cfm import CfmResult
from openquery.sources.br.cfm import CfmSource


class TestCfmResult:
    def test_default_values(self):
        data = CfmResult()
        assert data.crm_number == ""
        assert data.nome == ""
        assert data.specialty == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CfmResult(
            crm_number="SP-123456",
            nome="Dr. Ana Costa",
            specialty="Cardiologia",
            status="Ativo",
        )
        restored = CfmResult.model_validate_json(data.model_dump_json())
        assert restored.crm_number == "SP-123456"
        assert restored.specialty == "Cardiologia"

    def test_audit_excluded_from_json(self):
        data = CfmResult(crm_number="SP-123", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestCfmSourceMeta:
    def test_meta_name(self):
        assert CfmSource().meta().name == "br.cfm"

    def test_meta_country(self):
        assert CfmSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        assert CfmSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert CfmSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert CfmSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nome(self):
        source = CfmSource()
        page = self._make_page("Nome: Dr. Ana Costa\nEspecialidade: Cardiologia\nSituação: Ativo\n")
        result = source._parse_result(page, "SP-123456")
        assert result.nome == "Dr. Ana Costa"

    def test_parse_specialty(self):
        source = CfmSource()
        page = self._make_page("Nome: Test\nEspecialidade: Pediatria\nSituação: Ativo\n")
        result = source._parse_result(page, "RJ-789")
        assert result.specialty == "Pediatria"

    def test_parse_status(self):
        source = CfmSource()
        page = self._make_page("Nome: Test\nEspecialidade: X\nSituação: Cancelado\n")
        result = source._parse_result(page, "MG-001")
        assert result.status == "Cancelado"

    def test_parse_preserves_crm(self):
        source = CfmSource()
        page = self._make_page("Não encontrado.")
        result = source._parse_result(page, "SP-99999")
        assert result.crm_number == "SP-99999"
