"""Tests for us.epa_envirofacts — EPA Envirofacts environmental facility data."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

MOCK_EPA_RESPONSE = [
    {
        "FAC_NAME": "ACME CHEMICAL PLANT",
        "FAC_COMPLIANCE_STATUS": "In Violation",
        "FAC_VIOLATION_STATUS": "Active",
        "FAC_STATE": "TX",
    },
    {
        "FAC_NAME": "ACME CHEMICAL PLANT 2",
        "FAC_COMPLIANCE_STATUS": "No Violation",
        "FAC_VIOLATION_STATUS": "",
        "FAC_STATE": "TX",
    },
]


class TestEpaEnvirofactsResult:
    def test_defaults(self):
        from openquery.models.us.epa_envirofacts import EpaEnvirofactsResult

        r = EpaEnvirofactsResult()
        assert r.search_term == ""
        assert r.facility_name == ""
        assert r.compliance_status == ""
        assert r.violations == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.epa_envirofacts import EpaEnvirofactsResult

        r = EpaEnvirofactsResult(
            search_term="ACME",
            facility_name="ACME CHEMICAL PLANT",
            compliance_status="In Violation",
            violations=["Active violation"],
        )
        dumped = r.model_dump_json()
        restored = EpaEnvirofactsResult.model_validate_json(dumped)
        assert restored.search_term == "ACME"
        assert restored.compliance_status == "In Violation"
        assert len(restored.violations) == 1

    def test_audit_excluded_from_json(self):
        from openquery.models.us.epa_envirofacts import EpaEnvirofactsResult

        r = EpaEnvirofactsResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()


class TestEpaEnvirofactsSourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        assert EpaEnvirofactsSource().meta().name == "us.epa_envirofacts"

    def test_meta_country(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        assert EpaEnvirofactsSource().meta().country == "US"

    def test_meta_no_browser(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        meta = EpaEnvirofactsSource().meta()
        assert meta.requires_browser is False
        assert meta.requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        assert EpaEnvirofactsSource().meta().rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        assert DocumentType.CUSTOM in EpaEnvirofactsSource().meta().supported_inputs


class TestEpaEnvirofactsParseResult:
    def _make_input(self, name: str = "ACME") -> QueryInput:
        return QueryInput(
            document_number=name,
            document_type=DocumentType.CUSTOM,
            extra={"facility_name": name},
        )

    def test_empty_term_raises(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        with pytest.raises(SourceError, match="us.epa_envirofacts"):
            EpaEnvirofactsSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_successful_query(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_EPA_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = EpaEnvirofactsSource().query(self._make_input())

        assert result.search_term == "ACME"
        assert result.facility_name == "ACME CHEMICAL PLANT"
        assert result.compliance_status == "In Violation"
        assert "Active" in result.violations

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="us.epa_envirofacts"):
                EpaEnvirofactsSource().query(self._make_input())

    def test_empty_response_returns_result(self):
        from openquery.sources.us.epa_envirofacts import EpaEnvirofactsSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = EpaEnvirofactsSource().query(self._make_input())

        assert result.facility_name == ""
        assert result.violations == []
