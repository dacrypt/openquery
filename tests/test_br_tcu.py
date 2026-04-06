"""Tests for br.tcu — TCU government sanctions (licitantes inidôneos)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestBrTcuResult — model tests
# ===========================================================================


class TestBrTcuResult:
    def test_defaults(self):
        from openquery.models.br.tcu import BrTcuResult

        r = BrTcuResult()
        assert r.search_term == ""
        assert r.company_name == ""
        assert r.cnpj == ""
        assert r.sanction_status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.tcu import BrTcuResult

        r = BrTcuResult(
            search_term="Empresa Teste",
            company_name="Empresa Teste Ltda",
            cnpj="12345678000195",
            sanction_status="ineligible",
        )
        restored = BrTcuResult.model_validate_json(r.model_dump_json())
        assert restored.company_name == "Empresa Teste Ltda"
        assert restored.sanction_status == "ineligible"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.tcu import BrTcuResult

        r = BrTcuResult(audit="evidence")
        assert "audit" not in r.model_dump()


# ===========================================================================
# TestBrTcuSourceMeta
# ===========================================================================


class TestBrTcuSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().name == "br.tcu"

    def test_meta_country(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().country == "BR"

    def test_meta_no_browser(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.br.tcu import BrTcuSource

        assert BrTcuSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestBrTcuParseResult — parsing logic
# ===========================================================================


class TestBrTcuParseResult:
    def test_missing_search_raises(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_parse_empty_list(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        result = src._parse_response([], "test")
        assert result.sanction_status == "clear"

    def test_parse_list_response(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        data = [
            {
                "nome": "Empresa Corrupta SA",
                "cpfCnpj": "12345678000195",
                "situacao": "INIDÔNEO",
            }
        ]
        result = src._parse_response(data, "Empresa Corrupta SA")
        assert result.company_name == "Empresa Corrupta SA"
        assert result.cnpj == "12345678000195"
        assert "INIDÔNEO" in result.sanction_status

    def test_parse_paginated_dict(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        data = {
            "content": [
                {"nomeRazaoSocial": "Empresa XYZ", "cpfCnpj": "98765432000100", "situacao": "active"}
            ]
        }
        result = src._parse_response(data, "XYZ")
        assert result.company_name == "Empresa XYZ"

    def test_http_404_returns_not_found(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = src._query("unknown")

        assert result.sanction_status == "not_found"


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestBrTcuIntegration:
    def test_query_company(self):
        from openquery.sources.br.tcu import BrTcuSource

        src = BrTcuSource()
        result = src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="Empresa Teste",
        ))
        assert isinstance(result.sanction_status, str)
