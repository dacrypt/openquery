"""Unit tests for br.oab — OAB lawyer verification."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.oab import OabResult
from openquery.sources.br.oab import OabSource


class TestOabResult:
    def test_default_values(self):
        data = OabResult()
        assert data.oab_number == ""
        assert data.nome == ""
        assert data.estado == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = OabResult(
            oab_number="123456",
            nome="Dr. João Silva",
            estado="SP",
            status="Ativo",
        )
        restored = OabResult.model_validate_json(data.model_dump_json())
        assert restored.oab_number == "123456"
        assert restored.nome == "Dr. João Silva"
        assert restored.estado == "SP"

    def test_audit_excluded_from_json(self):
        data = OabResult(oab_number="123", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestOabSourceMeta:
    def test_meta_name(self):
        assert OabSource().meta().name == "br.oab"

    def test_meta_country(self):
        assert OabSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        assert OabSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        assert OabSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert OabSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_nome(self):
        source = OabSource()
        page = self._make_page("Nome: Dr. João Silva\nUF: SP\nSituação: Ativo\n")
        result = source._parse_result(page, "123456")
        assert result.nome == "Dr. João Silva"

    def test_parse_estado(self):
        source = OabSource()
        page = self._make_page("Nome: ABC\nUF: RJ\nSituação: Ativo\n")
        result = source._parse_result(page, "789")
        assert result.estado == "RJ"

    def test_parse_status(self):
        source = OabSource()
        page = self._make_page("Nome: ABC\nUF: MG\nSituação: Suspenso\n")
        result = source._parse_result(page, "001")
        assert result.status == "Suspenso"

    def test_parse_preserves_oab_number(self):
        source = OabSource()
        page = self._make_page("Não encontrado.")
        result = source._parse_result(page, "999999")
        assert result.oab_number == "999999"
