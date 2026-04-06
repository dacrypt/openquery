"""Unit tests for br.crea — CREA engineer registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.crea import CreaResult
from openquery.sources.br.crea import CreaSource


class TestCreaResult:
    def test_default_values(self):
        data = CreaResult()
        assert data.crea_number == ""
        assert data.nome == ""
        assert data.specialty == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CreaResult(
            crea_number="SP-123456",
            nome="Eng. Carlos Souza",
            specialty="Engenharia Civil",
            status="Ativo",
        )
        restored = CreaResult.model_validate_json(data.model_dump_json())
        assert restored.crea_number == "SP-123456"
        assert restored.specialty == "Engenharia Civil"

    def test_audit_excluded_from_json(self):
        data = CreaResult(crea_number="123", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestCreaSourceMeta:
    def test_meta_name(self):
        assert CreaSource().meta().name == "br.crea"

    def test_meta_country(self):
        assert CreaSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        assert CreaSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert CreaSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert CreaSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nome(self):
        source = CreaSource()
        page = self._make_page("Nome: Eng. Carlos Souza\nEspecialidade: Civil\nSituação: Ativo\n")
        result = source._parse_result(page, "SP-123456")
        assert result.nome == "Eng. Carlos Souza"

    def test_parse_specialty(self):
        source = CreaSource()
        page = self._make_page("Nome: Test\nEspecialidade: Elétrica\nSituação: Ativo\n")
        result = source._parse_result(page, "RJ-001")
        assert result.specialty == "Elétrica"

    def test_parse_status(self):
        source = CreaSource()
        page = self._make_page("Nome: Test\nEspecialidade: X\nSituação: Inativo\n")
        result = source._parse_result(page, "MG-002")
        assert result.status == "Inativo"

    def test_parse_preserves_crea_number(self):
        source = CreaSource()
        page = self._make_page("Não encontrado.")
        result = source._parse_result(page, "SP-99999")
        assert result.crea_number == "SP-99999"
