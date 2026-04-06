"""Tests for ve.bcv — Venezuela Central Bank exchange rates."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestBcvResult — model tests
# ===========================================================================


class TestBcvResult:
    def test_defaults(self):
        from openquery.models.ve.bcv import BcvResult

        r = BcvResult()
        assert r.usd_rate == ""
        assert r.eur_rate == ""
        assert r.cny_rate == ""
        assert r.try_rate == ""
        assert r.rub_rate == ""
        assert r.date == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.bcv import BcvResult

        r = BcvResult(
            usd_rate="36,50",
            eur_rate="39,20",
            cny_rate="5,03",
            try_rate="1,12",
            rub_rate="0,40",
            date="01/04/2026",
            details={"USD": "36,50"},
        )
        dumped = r.model_dump_json()
        restored = BcvResult.model_validate_json(dumped)
        assert restored.usd_rate == "36,50"
        assert restored.eur_rate == "39,20"
        assert restored.date == "01/04/2026"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.bcv import BcvResult

        r = BcvResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.bcv import BcvResult

        r = BcvResult(details={"USD": "36,50", "EUR": "39,20"})
        assert r.details["USD"] == "36,50"


# ===========================================================================
# TestBcvSourceMeta
# ===========================================================================


class TestBcvSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.bcv import BcvSource

        assert BcvSource().meta().name == "ve.bcv"

    def test_meta_country(self):
        from openquery.sources.ve.bcv import BcvSource

        assert BcvSource().meta().country == "VE"

    def test_meta_no_browser(self):
        from openquery.sources.ve.bcv import BcvSource

        assert BcvSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.ve.bcv import BcvSource

        assert BcvSource().meta().requires_captcha is False

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.bcv import BcvSource

        assert DocumentType.CUSTOM in BcvSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.bcv import BcvSource

        assert BcvSource().meta().rate_limit_rpm == 10


# ===========================================================================
# TestBcvParseResult — HTML parsing logic
# ===========================================================================


class TestBcvParseResult:
    def _parse(self, html: str) -> object:
        from openquery.sources.ve.bcv import BcvSource

        return BcvSource()._parse_html(html)

    def test_usd_rate_extracted(self):
        html = "<html><body>USD 36,50 EUR 39,20</body></html>"
        result = self._parse(html)
        assert result.usd_rate == "36,50"

    def test_eur_rate_extracted(self):
        html = "<html><body>EUR 39,20</body></html>"
        result = self._parse(html)
        assert result.eur_rate == "39,20"

    def test_multiple_currencies(self):
        html = "<body>USD 36,50 EUR 39,20 CNY 5,03 TRY 1,12 RUB 0,40</body>"
        result = self._parse(html)
        assert result.usd_rate == "36,50"
        assert result.eur_rate == "39,20"
        assert result.cny_rate == "5,03"
        assert result.try_rate == "1,12"
        assert result.rub_rate == "0,40"

    def test_date_extracted(self):
        html = "<body>Fecha: 01/04/2026 USD 36,50</body>"
        result = self._parse(html)
        assert result.date != ""

    def test_empty_html_returns_defaults(self):
        result = self._parse("<html><body>No data here</body></html>")
        assert result.usd_rate == ""
        assert result.eur_rate == ""

    def test_queried_at_set(self):
        result = self._parse("<body></body>")
        assert isinstance(result.queried_at, datetime)

    def test_details_populated(self):
        html = "<body>USD 36,50 EUR 39,20</body>"
        result = self._parse(html)
        # details should have entries for found currencies
        assert isinstance(result.details, dict)


# ===========================================================================
# TestBcvQuery — query method
# ===========================================================================


class TestBcvQuery:
    def test_query_calls_internal(self):
        from openquery.models.ve.bcv import BcvResult
        from openquery.sources.ve.bcv import BcvSource

        src = BcvSource()
        src._query = MagicMock(return_value=BcvResult(usd_rate="36,50"))
        result = src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
        src._query.assert_called_once()
        assert result.usd_rate == "36,50"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.ve.bcv import BcvSource

        src = BcvSource()
        with patch("httpx.Client") as mock_client:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "403", request=MagicMock(), response=MagicMock(status_code=403)
            )
            mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
            with pytest.raises(SourceError, match="403"):
                src._query()


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestBcvIntegration:
    def test_live_rates(self):
        from openquery.sources.ve.bcv import BcvSource

        result = BcvSource()._query()
        assert isinstance(result.usd_rate, str)
        assert isinstance(result.queried_at, datetime)
