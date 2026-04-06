"""Tests for br.tse_candidatos — Brazil TSE candidate/politician lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestTseCandidatosResult — model tests
# ===========================================================================


class TestTseCandidatosResult:
    def test_defaults(self):
        from openquery.models.br.tse_candidatos import BrTseCandidatosResult

        r = BrTseCandidatosResult()
        assert r.search_term == ""
        assert r.candidate_name == ""
        assert r.cpf == ""
        assert r.party == ""
        assert r.position == ""
        assert r.election_year == ""
        assert r.declared_assets == ""
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.tse_candidatos import BrTseCandidatosResult

        r = BrTseCandidatosResult(
            search_term="Lula",
            candidate_name="LUIZ INÁCIO LULA DA SILVA",
            party="PT",
            position="PRESIDENTE",
            election_year="2022",
            declared_assets="5000000.00",
        )
        dumped = r.model_dump_json()
        restored = BrTseCandidatosResult.model_validate_json(dumped)
        assert restored.search_term == "Lula"
        assert restored.candidate_name == "LUIZ INÁCIO LULA DA SILVA"
        assert restored.party == "PT"
        assert restored.election_year == "2022"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.tse_candidatos import BrTseCandidatosResult

        r = BrTseCandidatosResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestTseCandidatosSourceMeta
# ===========================================================================


class TestTseCandidatosSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        assert BrTseCandidatosSource().meta().name == "br.tse_candidatos"

    def test_meta_country(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        assert BrTseCandidatosSource().meta().country == "BR"

    def test_meta_no_captcha_no_browser(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        meta = BrTseCandidatosSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        assert BrTseCandidatosSource().meta().rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        assert DocumentType.CUSTOM in BrTseCandidatosSource().meta().supported_inputs


# ===========================================================================
# TestTseCandidatosParseResult
# ===========================================================================

MOCK_TSE_RESPONSE = {
    "result": {
        "total": 2,
        "records": [
            {
                "NM_CANDIDATO": "LUIZ INÁCIO LULA DA SILVA",
                "NR_CPF_CANDIDATO": "12345678900",
                "SG_PARTIDO": "PT",
                "DS_CARGO": "PRESIDENTE",
                "ANO_ELEICAO": 2022,
                "VR_BEM_CANDIDATO": "5000000.00",
            },
            {
                "NM_CANDIDATO": "LULA JUNIOR",
                "NR_CPF_CANDIDATO": "98765432100",
                "SG_PARTIDO": "PT",
                "DS_CARGO": "VEREADOR",
                "ANO_ELEICAO": 2020,
                "VR_BEM_CANDIDATO": "10000.00",
            },
        ],
    }
}


class TestTseCandidatosParseResult:
    def _make_input(self, name: str = "Lula") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"name": name},
        )

    def test_successful_search_returns_first_match(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TSE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = BrTseCandidatosSource().query(self._make_input("Lula"))

        assert result.search_term == "Lula"
        assert result.candidate_name == "LUIZ INÁCIO LULA DA SILVA"
        assert result.party == "PT"
        assert result.position == "PRESIDENTE"
        assert result.election_year == "2022"
        assert result.declared_assets == "5000000.00"

    def test_no_results_returns_empty(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"total": 0, "records": []}}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = BrTseCandidatosSource().query(self._make_input("NonExistent"))

        assert result.candidate_name == ""
        assert "No candidates found" in result.details

    def test_missing_input_raises(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        source = BrTseCandidatosSource()
        inp = QueryInput(document_number="", document_type=DocumentType.CUSTOM, extra={})
        with pytest.raises(SourceError, match="br.tse_candidatos"):
            source.query(inp)

    def test_cpf_input_used_as_search_term(self):
        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TSE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            inp = QueryInput(
                document_number="12345678900",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = BrTseCandidatosSource().query(inp)

        assert result.search_term == "12345678900"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.br.tse_candidatos import BrTseCandidatosSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="br.tse_candidatos"):
                BrTseCandidatosSource().query(self._make_input())
