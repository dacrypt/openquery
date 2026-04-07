"""Tests for co.peajes_tarifas — Colombian toll booth tariffs.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestCoPeajesTarifasResult — model tests
# ===========================================================================


class TestCoPeajesTarifasResult:
    def test_defaults(self):
        from openquery.models.co.peajes_tarifas import CoPeajesTarifasResult

        r = CoPeajesTarifasResult()
        assert r.peaje == ""
        assert r.categoria == ""
        assert r.tarifa == ""
        assert r.ruta == ""
        assert r.details == ""
        assert r.records == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.peajes_tarifas import CoPeajesTarifasResult

        r = CoPeajesTarifasResult(
            peaje="BUENAVISTA",
            categoria="I",
            tarifa="9800",
            ruta="Bogota-Villavicencio",
        )
        dumped = r.model_dump_json()
        restored = CoPeajesTarifasResult.model_validate_json(dumped)
        assert restored.peaje == "BUENAVISTA"
        assert restored.tarifa == "9800"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.peajes_tarifas import CoPeajesTarifasResult

        r = CoPeajesTarifasResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestCoPeajesTarifasSourceMeta
# ===========================================================================


class TestCoPeajesTarifasSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        meta = PeajesTarifasSource().meta()
        assert meta.name == "co.peajes_tarifas"

    def test_meta_country(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        meta = PeajesTarifasSource().meta()
        assert meta.country == "CO"

    def test_meta_no_captcha(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        meta = PeajesTarifasSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        meta = PeajesTarifasSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        meta = PeajesTarifasSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestCoPeajesTarifasParseResult
# ===========================================================================

MOCK_INVIAS_RESPONSE = [
    {
        "peaje": "BUENAVISTA",
        "categoria": "I",
        "tarifa": "9800",
        "ruta": "Bogota-Villavicencio",
        "departamento": "META",
    },
    {
        "peaje": "BUENAVISTA",
        "categoria": "II",
        "tarifa": "13200",
        "ruta": "Bogota-Villavicencio",
        "departamento": "META",
    },
]


class TestCoPeajesTarifasParseResult:
    def _make_input(self, peaje: str = "BUENAVISTA", categoria: str = "I") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"peaje": peaje, "categoria": categoria},
        )

    def test_missing_peaje_and_categoria_raises(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        source = PeajesTarifasSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="peaje"):
            source.query(inp)

    def test_successful_query(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INVIAS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = PeajesTarifasSource()
            result = source.query(self._make_input())

        assert result.peaje == "BUENAVISTA"
        assert result.categoria == "I"
        assert result.tarifa == "9800"
        assert result.ruta == "Bogota-Villavicencio"
        assert len(result.records) == 2

    def test_query_by_peaje_only(self):
        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_INVIAS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = PeajesTarifasSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"peaje": "BUENAVISTA"},
            )
            result = source.query(inp)

        assert result.peaje == "BUENAVISTA"
        assert len(result.records) == 2

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.co.peajes_tarifas import PeajesTarifasSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = PeajesTarifasSource()
            with pytest.raises(SourceError, match="co.peajes_tarifas"):
                source.query(self._make_input())
