"""Tests for co.combustible_precios — Colombian fuel prices by city.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestCoCombustiblePreciosResult — model tests
# ===========================================================================


class TestCoCombustiblePreciosResult:
    def test_defaults(self):
        from openquery.models.co.combustible_precios import CoCombustiblePreciosResult

        r = CoCombustiblePreciosResult()
        assert r.ciudad == ""
        assert r.combustible == ""
        assert r.precio_galon == ""
        assert r.fecha == ""
        assert r.details == ""
        assert r.records == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.combustible_precios import CoCombustiblePreciosResult

        r = CoCombustiblePreciosResult(
            ciudad="BOGOTA",
            combustible="gasolina",
            precio_galon="12500",
        )
        dumped = r.model_dump_json()
        restored = CoCombustiblePreciosResult.model_validate_json(dumped)
        assert restored.ciudad == "BOGOTA"
        assert restored.precio_galon == "12500"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.combustible_precios import CoCombustiblePreciosResult

        r = CoCombustiblePreciosResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestCoCombustiblePreciosSourceMeta
# ===========================================================================


class TestCoCombustiblePreciosSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        meta = CombustiblePreciosSource().meta()
        assert meta.name == "co.combustible_precios"

    def test_meta_country(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        meta = CombustiblePreciosSource().meta()
        assert meta.country == "CO"

    def test_meta_no_captcha(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        meta = CombustiblePreciosSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        meta = CombustiblePreciosSource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        meta = CombustiblePreciosSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestCoCombustiblePreciosParseResult
# ===========================================================================

MOCK_SOCRATA_RESPONSE = [
    {
        "municipio": "BOGOTA",
        "departamento": "CUNDINAMARCA",
        "combustible": "GASOLINA CORRIENTE",
        "precio": "12500",
        "fecha": "2024-01-01T00:00:00.000",
    },
    {
        "municipio": "BOGOTA",
        "departamento": "CUNDINAMARCA",
        "combustible": "GASOLINA EXTRA",
        "precio": "13800",
        "fecha": "2024-01-01T00:00:00.000",
    },
]


class TestCoCombustiblePreciosParseResult:
    def _make_input(self, ciudad: str = "BOGOTA", combustible: str = "gasolina") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"ciudad": ciudad, "combustible": combustible},
        )

    def test_missing_ciudad_and_combustible_raises(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        source = CombustiblePreciosSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="ciudad"):
            source.query(inp)

    def test_successful_query(self):
        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SOCRATA_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CombustiblePreciosSource()
            result = source.query(self._make_input())

        assert result.ciudad == "BOGOTA"
        assert len(result.records) == 2
        assert "12500" in result.precio_galon
        assert "2" in result.details

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.co.combustible_precios import CombustiblePreciosSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CombustiblePreciosSource()
            with pytest.raises(SourceError, match="co.combustible_precios"):
                source.query(self._make_input())
