"""Unit tests for br.fipe — Brazil FIPE vehicle price source."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.models.br.fipe import BrFipeResult
from openquery.sources.br.fipe import BrFipeSource
from openquery.sources.base import DocumentType, QueryInput


class TestBrFipeResult:
    def test_default_values(self):
        r = BrFipeResult()
        assert r.codigo_fipe == ""
        assert r.marca == ""
        assert r.modelo == ""
        assert r.ano == ""
        assert r.combustivel == ""
        assert r.valor == ""
        assert r.mes_referencia == ""
        assert r.tipo_veiculo == 0

    def test_round_trip(self):
        r = BrFipeResult(
            codigo_fipe="001004-9",
            marca="FIAT",
            modelo="PALIO Weekend Stile 1.6 mpi 16V",
            ano="2003",
            combustivel="Gasolina",
            valor="R$ 14.741,00",
            mes_referencia="março de 2024",
            tipo_veiculo=1,
        )
        restored = BrFipeResult.model_validate_json(r.model_dump_json())
        assert restored.codigo_fipe == "001004-9"
        assert restored.marca == "FIAT"
        assert restored.valor == "R$ 14.741,00"

    def test_audit_excluded_from_serialization(self):
        r = BrFipeResult(codigo_fipe="001004-9", audit={"screenshot": "base64data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_queried_at_defaults_to_now(self):
        before = datetime.now()
        r = BrFipeResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestBrFipeSourceMeta:
    def test_meta_name_and_country(self):
        src = BrFipeSource()
        meta = src.meta()
        assert meta.name == "br.fipe"
        assert meta.country == "BR"

    def test_meta_no_captcha_no_browser(self):
        src = BrFipeSource()
        meta = src.meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_supported_inputs(self):
        src = BrFipeSource()
        meta = src.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        src = BrFipeSource()
        meta = src.meta()
        assert meta.rate_limit_rpm == 30


class TestBrFipeParseResult:
    def _make_input(self, codigo: str) -> QueryInput:
        return QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number=codigo,
        )

    def _api_response(self) -> list[dict]:
        return [
            {
                "valor": "R$ 14.741,00",
                "marca": "FIAT",
                "modelo": "PALIO Weekend Stile 1.6 mpi 16V",
                "anoModelo": 2003,
                "combustivel": "Gasolina",
                "codigoFipe": "001004-9",
                "mesReferencia": "março de 2024",
                "tipoVeiculo": 1,
                "siglaCombustivel": "G",
                "dataConsulta": "sábado, 15 de março de 2024 10:30",
            }
        ]

    @patch("openquery.sources.br.fipe.httpx.Client")
    def test_query_returns_result(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._api_response()
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        src = BrFipeSource()
        result = src.query(self._make_input("001004-9"))

        assert isinstance(result, BrFipeResult)
        assert result.codigo_fipe == "001004-9"
        assert result.marca == "FIAT"
        assert result.valor == "R$ 14.741,00"
        assert result.combustivel == "Gasolina"
        assert result.ano == "2003"

    @patch("openquery.sources.br.fipe.httpx.Client")
    def test_query_dict_response(self, mock_client_cls):
        """API may return a dict instead of a list."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._api_response()[0]
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        src = BrFipeSource()
        result = src.query(self._make_input("001004-9"))

        assert isinstance(result, BrFipeResult)
        assert result.codigo_fipe == "001004-9"

    @patch("openquery.sources.br.fipe.httpx.Client")
    def test_query_not_found_returns_empty(self, mock_client_cls):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        src = BrFipeSource()
        result = src.query(self._make_input("999999-9"))

        assert isinstance(result, BrFipeResult)
        assert result.codigo_fipe == "999999-9"
        assert result.marca == ""

    @patch("openquery.sources.br.fipe.httpx.Client")
    def test_query_http_error_raises_source_error(self, mock_client_cls):
        import httpx

        from openquery.exceptions import SourceError

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        http_err = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_resp
        )
        mock_resp.raise_for_status.side_effect = http_err
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        src = BrFipeSource()
        with pytest.raises(SourceError, match="br.fipe"):
            src.query(self._make_input("001004-9"))

    def test_query_missing_codigo_raises_source_error(self):
        from openquery.exceptions import SourceError

        src = BrFipeSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        with pytest.raises(SourceError, match="br.fipe"):
            src.query(inp)

    @patch("openquery.sources.br.fipe.httpx.Client")
    def test_query_uses_extra_codigo_fipe(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._api_response()
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        src = BrFipeSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"codigo_fipe": "001004-9"},
        )
        result = src.query(inp)
        assert result.codigo_fipe == "001004-9"

    @pytest.mark.integration
    def test_integration_real_fipe_code(self):
        """Hit real BrasilAPI with a known FIPE code."""
        src = BrFipeSource()
        result = src.query(self._make_input("001004-9"))
        assert result.marca != ""
        assert result.valor.startswith("R$")
