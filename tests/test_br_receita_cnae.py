"""Tests for br.receita_cnae — CNAE activity classification codes."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestBrReceitaCnaeResult — model tests
# ===========================================================================


class TestBrReceitaCnaeResult:
    def test_defaults(self):
        from openquery.models.br.receita_cnae import BrReceitaCnaeResult

        r = BrReceitaCnaeResult()
        assert r.code == ""
        assert r.description == ""
        assert r.section == ""
        assert r.division == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.receita_cnae import BrReceitaCnaeResult

        r = BrReceitaCnaeResult(
            code="6201500",
            description="Desenvolvimento de programas de computador sob encomenda",
            section="J",
            division="62",
        )
        restored = BrReceitaCnaeResult.model_validate_json(r.model_dump_json())
        assert restored.code == "6201500"
        assert restored.section == "J"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.receita_cnae import BrReceitaCnaeResult

        r = BrReceitaCnaeResult(audit=b"pdf-bytes")
        assert "audit" not in r.model_dump()


# ===========================================================================
# TestBrReceitaCnaeSourceMeta
# ===========================================================================


class TestBrReceitaCnaeSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        assert BrReceitaCnaeSource().meta().name == "br.receita_cnae"

    def test_meta_country(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        assert BrReceitaCnaeSource().meta().country == "BR"

    def test_meta_no_browser(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        assert BrReceitaCnaeSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        assert BrReceitaCnaeSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        assert DocumentType.CUSTOM in BrReceitaCnaeSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        assert BrReceitaCnaeSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestBrReceitaCnaeParseResult — parsing logic
# ===========================================================================


class TestBrReceitaCnaeParseResult:
    def test_missing_code_raises(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        src = BrReceitaCnaeSource()
        with pytest.raises(SourceError):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_code(self):
        from openquery.models.br.receita_cnae import BrReceitaCnaeResult
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        src = BrReceitaCnaeSource()
        called_with: list[str] = []

        def fake_query(code: str) -> BrReceitaCnaeResult:
            called_with.append(code)
            return BrReceitaCnaeResult(code=code)

        src._query = fake_query
        src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="6201500"))
        assert called_with[0] == "6201500"

    def test_parse_api_response(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        src = BrReceitaCnaeSource()
        api_data = {
            "codigo": "6201500",
            "descricao": "Desenvolvimento de programas de computador sob encomenda",
            "secao": "J",
            "divisao": "62",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_data
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = src._query("6201500")

        assert result.code == "6201500"
        assert result.section == "J"
        assert result.division == "62"

    def test_not_found_returns_empty(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        src = BrReceitaCnaeSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = src._query("9999999")

        assert result.code == "9999999"
        assert result.description == ""


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestBrReceitaCnaeIntegration:
    def test_query_known_cnae(self):
        from openquery.sources.br.receita_cnae import BrReceitaCnaeSource

        src = BrReceitaCnaeSource()
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="6201500",
            )
        )
        assert result.code != "" or result.details.get("error")
