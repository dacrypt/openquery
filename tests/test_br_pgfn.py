"""Unit tests for br.pgfn — PGFN tax debt registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.br.pgfn import PgfnResult
from openquery.sources.br.pgfn import PgfnSource


class TestPgfnResult:
    def test_default_values(self):
        data = PgfnResult()
        assert data.search_term == ""
        assert data.total_debt == ""
        assert data.debt_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PgfnResult(
            search_term="123.456.789-00",
            total_debt="R$ 15.000,00",
            debt_status="Com débito",
        )
        restored = PgfnResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "123.456.789-00"
        assert restored.debt_status == "Com débito"

    def test_audit_excluded_from_json(self):
        data = PgfnResult(search_term="123", audit={"pdf": "bytes"})
        assert "audit" not in data.model_dump_json()
        assert data.audit == {"pdf": "bytes"}


class TestPgfnSourceMeta:
    def test_meta_name(self):
        assert PgfnSource().meta().name == "br.pgfn"

    def test_meta_country(self):
        assert PgfnSource().meta().country == "BR"

    def test_meta_requires_browser(self):
        assert PgfnSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert PgfnSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert PgfnSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert PgfnSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_sem_debito(self):
        source = PgfnSource()
        page = self._make_page("Situação: Sem débito ativo.\nContribuinte regularizado.\n")
        result = source._parse_result(page, "12345678000100")
        assert "sem débito" in result.debt_status.lower() or result.debt_status == "Sem débito"

    def test_parse_com_debito(self):
        source = PgfnSource()
        page = self._make_page("Situação: Com débito ativo.\nTotal: R$ 5.000,00\n")
        result = source._parse_result(page, "12345678000100")
        assert result.debt_status != ""

    def test_parse_total_debt(self):
        source = PgfnSource()
        page = self._make_page("Total: R$ 15.000,00\nSituação: Pendente\n")
        result = source._parse_result(page, "123")
        assert result.total_debt == "R$ 15.000,00"

    def test_parse_preserves_search_term(self):
        source = PgfnSource()
        page = self._make_page("Sem resultados.")
        result = source._parse_result(page, "98765432100")
        assert result.search_term == "98765432100"
