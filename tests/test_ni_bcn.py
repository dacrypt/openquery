"""Tests for ni.bcn — Nicaragua BCN exchange rates."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestNiBcnResult:
    def test_defaults(self):
        from openquery.models.ni.bcn import NiBcnResult

        r = NiBcnResult()
        assert r.usd_rate == ""
        assert r.date == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ni.bcn import NiBcnResult

        r = NiBcnResult(usd_rate="36.5432", date="01/04/2026", details={"USD": "36.5432"})
        dumped = r.model_dump_json()
        restored = NiBcnResult.model_validate_json(dumped)
        assert restored.usd_rate == "36.5432"
        assert restored.date == "01/04/2026"

    def test_audit_excluded_from_json(self):
        from openquery.models.ni.bcn import NiBcnResult

        r = NiBcnResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ni.bcn import NiBcnResult

        r = NiBcnResult(details={"USD": "36.5432", "fecha": "01/04/2026"})
        assert r.details["USD"] == "36.5432"


class TestNiBcnSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ni.bcn import NiBcnSource

        assert NiBcnSource().meta().name == "ni.bcn"

    def test_meta_country(self):
        from openquery.sources.ni.bcn import NiBcnSource

        assert NiBcnSource().meta().country == "NI"

    def test_meta_no_browser(self):
        from openquery.sources.ni.bcn import NiBcnSource

        assert NiBcnSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.ni.bcn import NiBcnSource

        assert NiBcnSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ni.bcn import NiBcnSource

        assert DocumentType.CUSTOM in NiBcnSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ni.bcn import NiBcnSource

        assert NiBcnSource().meta().rate_limit_rpm == 10


class TestNiBcnParseResult:
    def _parse(self, html: str) -> object:
        from openquery.sources.ni.bcn import NiBcnSource

        return NiBcnSource()._parse_html(html)

    def test_usd_rate_extracted(self):
        html = "<html><body>Dólar 36.5432 córdobas</body></html>"
        result = self._parse(html)
        assert result.usd_rate == "36.5432"

    def test_date_extracted(self):
        html = "<body>Fecha: 01/04/2026 Dólar 36.5432</body>"
        result = self._parse(html)
        assert result.date != ""

    def test_empty_html_returns_defaults(self):
        result = self._parse("<html><body>No data here</body></html>")
        assert result.usd_rate == ""

    def test_queried_at_set(self):
        result = self._parse("<body></body>")
        assert isinstance(result.queried_at, datetime)

    def test_details_populated(self):
        html = "<body>USD 36.5432 fecha 01/04/2026</body>"
        result = self._parse(html)
        assert isinstance(result.details, dict)

    def test_fallback_rate_pattern(self):
        html = "<body>Tipo de cambio oficial: 36.5432</body>"
        result = self._parse(html)
        assert result.usd_rate == "36.5432"


class TestNiBcnQuery:
    def test_query_calls_internal(self):
        from openquery.models.ni.bcn import NiBcnResult
        from openquery.sources.ni.bcn import NiBcnSource

        src = NiBcnSource()
        src._query = MagicMock(return_value=NiBcnResult(usd_rate="36.5432"))
        result = src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
        src._query.assert_called_once()
        assert result.usd_rate == "36.5432"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.ni.bcn import NiBcnSource

        src = NiBcnSource()
        with patch("httpx.Client") as mock_client:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "503", request=MagicMock(), response=MagicMock(status_code=503)
            )
            mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
            with pytest.raises(SourceError, match="503"):
                src._query()


@pytest.mark.integration
class TestNiBcnIntegration:
    def test_live_rates(self):
        from openquery.sources.ni.bcn import NiBcnSource

        result = NiBcnSource()._query()
        assert isinstance(result.usd_rate, str)
        assert isinstance(result.queried_at, datetime)
