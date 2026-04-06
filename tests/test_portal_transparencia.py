"""Tests for br.portal_transparencia — Brazil federal transparency portal."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestPortalTransparenciaResult — model tests
# ===========================================================================


class TestPortalTransparenciaResult:
    def test_defaults(self):
        from openquery.models.br.portal_transparencia import BrPortalTransparenciaResult

        r = BrPortalTransparenciaResult()
        assert r.search_term == ""
        assert r.search_type == ""
        assert r.results_count == 0
        assert r.records == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.portal_transparencia import (
            BrPortalTransparenciaResult,
            TransparenciaRecord,
        )

        r = BrPortalTransparenciaResult(
            search_term="João Silva",
            search_type="servidores",
            results_count=1,
            records=[
                TransparenciaRecord(
                    nome="JOÃO SILVA",
                    cpf_cnpj="12345678900",
                    orgao="Ministério da Saúde",
                    cargo="Analista",
                    valor="8000.00",
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = BrPortalTransparenciaResult.model_validate_json(dumped)
        assert restored.search_term == "João Silva"
        assert restored.search_type == "servidores"
        assert restored.results_count == 1
        assert restored.records[0].nome == "JOÃO SILVA"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.portal_transparencia import BrPortalTransparenciaResult

        r = BrPortalTransparenciaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_record_defaults(self):
        from openquery.models.br.portal_transparencia import TransparenciaRecord

        rec = TransparenciaRecord()
        assert rec.nome == ""
        assert rec.cpf_cnpj == ""
        assert rec.orgao == ""
        assert rec.cargo == ""
        assert rec.valor == ""
        assert rec.details == ""


# ===========================================================================
# TestPortalTransparenciaSourceMeta
# ===========================================================================


class TestPortalTransparenciaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        assert BrPortalTransparenciaSource().meta().name == "br.portal_transparencia"

    def test_meta_country(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        assert BrPortalTransparenciaSource().meta().country == "BR"

    def test_meta_no_captcha_no_browser(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        meta = BrPortalTransparenciaSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        assert BrPortalTransparenciaSource().meta().rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        assert DocumentType.CUSTOM in BrPortalTransparenciaSource().meta().supported_inputs


# ===========================================================================
# TestPortalTransparenciaParseResult
# ===========================================================================

MOCK_SERVIDORES_RESPONSE = [
    {
        "nome": "JOÃO DA SILVA",
        "cpf": "12345678900",
        "orgao": {"nome": "Ministério da Saúde"},
        "cargo": {"nome": "Analista Técnico"},
        "remuneracaoBasicaBruta": "8000.00",
        "situacaoVinculo": "ATIVO PERMANENTE",
    },
    {
        "nome": "JOÃO SOUZA",
        "cpf": "98765432100",
        "orgao": {"nome": "Ministério da Educação"},
        "cargo": {"nome": "Professor"},
        "remuneracaoBasicaBruta": "6000.00",
        "situacaoVinculo": "ATIVO PERMANENTE",
    },
]


class TestPortalTransparenciaParseResult:
    def _make_input(self, name: str = "João Silva", search_type: str = "servidores") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"name": name, "search_type": search_type},
        )

    def test_successful_search_servidores(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SERVIDORES_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("httpx.Client") as mock_client_cls,
            patch("openquery.sources.br.portal_transparencia.get_settings") as mock_settings,
        ):
            mock_settings.return_value.br_transparencia_api_key = "test-key"
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = BrPortalTransparenciaSource().query(self._make_input())

        assert result.search_term == "João Silva"
        assert result.search_type == "servidores"
        assert result.results_count == 2
        assert result.records[0].nome == "JOÃO DA SILVA"
        assert result.records[0].orgao == "Ministério da Saúde"

    def test_missing_input_raises(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        source = BrPortalTransparenciaSource()
        inp = QueryInput(document_number="", document_type=DocumentType.CUSTOM, extra={})
        with pytest.raises(SourceError, match="br.portal_transparencia"):
            source.query(inp)

    def test_invalid_search_type_raises(self):
        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        source = BrPortalTransparenciaSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"name": "João", "search_type": "invalid"},
        )
        with patch("openquery.sources.br.portal_transparencia.get_settings") as mock_settings:
            mock_settings.return_value.br_transparencia_api_key = ""
            with pytest.raises(SourceError, match="br.portal_transparencia"):
                source.query(inp)

    def test_401_error_raises_descriptive_source_error(self):
        import httpx

        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )

        with (
            patch("httpx.Client") as mock_client_cls,
            patch("openquery.sources.br.portal_transparencia.get_settings") as mock_settings,
        ):
            mock_settings.return_value.br_transparencia_api_key = ""
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="API key"):
                BrPortalTransparenciaSource().query(self._make_input())

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.br.portal_transparencia import BrPortalTransparenciaSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with (
            patch("httpx.Client") as mock_client_cls,
            patch("openquery.sources.br.portal_transparencia.get_settings") as mock_settings,
        ):
            mock_settings.return_value.br_transparencia_api_key = ""
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="br.portal_transparencia"):
                BrPortalTransparenciaSource().query(self._make_input())
