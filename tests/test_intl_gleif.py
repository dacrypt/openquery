"""Tests for intl.gleif — GLEIF LEI registry lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestIntlGleifResult — model tests
# ===========================================================================


class TestIntlGleifResult:
    def test_defaults(self):
        from openquery.models.intl.gleif import IntlGleifResult

        r = IntlGleifResult()
        assert r.search_term == ""
        assert r.lei == ""
        assert r.legal_name == ""
        assert r.jurisdiction == ""
        assert r.entity_status == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.gleif import IntlGleifResult

        r = IntlGleifResult(
            search_term="Apple Inc",
            lei="HWUPKR0MPOU8FGXBT394",
            legal_name="Apple Inc.",
            jurisdiction="US",
            entity_status="ACTIVE",
        )
        restored = IntlGleifResult.model_validate_json(r.model_dump_json())
        assert restored.lei == "HWUPKR0MPOU8FGXBT394"
        assert restored.entity_status == "ACTIVE"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.gleif import IntlGleifResult

        r = IntlGleifResult(audit="evidence")
        assert "audit" not in r.model_dump()


# ===========================================================================
# TestIntlGleifSourceMeta
# ===========================================================================


class TestIntlGleifSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        assert IntlGleifSource().meta().name == "intl.gleif"

    def test_meta_country(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        assert IntlGleifSource().meta().country == "INTL"

    def test_meta_no_browser(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        assert IntlGleifSource().meta().requires_browser is False

    def test_meta_no_captcha(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        assert IntlGleifSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        assert IntlGleifSource().meta().rate_limit_rpm == 20


# ===========================================================================
# TestIntlGleifParseResult — parsing logic
# ===========================================================================


class TestIntlGleifParseResult:
    def test_missing_search_raises(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_lei_routing(self):
        """20-char alphanumeric triggers LEI direct lookup."""
        from openquery.models.intl.gleif import IntlGleifResult
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        called_lei: list[str] = []
        called_name: list[str] = []

        def fake_by_lei(lei: str) -> IntlGleifResult:
            called_lei.append(lei)
            return IntlGleifResult(lei=lei)

        def fake_by_name(name: str) -> IntlGleifResult:
            called_name.append(name)
            return IntlGleifResult(search_term=name)

        src._query_by_lei = fake_by_lei
        src._query_by_name = fake_by_name

        # 20-char alphanumeric — routes to LEI
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="HWUPKR0MPOU8FGXBT394",
            )
        )
        assert len(called_lei) == 1
        assert len(called_name) == 0

    def test_name_routing(self):
        from openquery.models.intl.gleif import IntlGleifResult
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        called_name: list[str] = []

        def fake_by_name(name: str) -> IntlGleifResult:
            called_name.append(name)
            return IntlGleifResult(search_term=name)

        src._query_by_name = fake_by_name
        src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="Apple Inc",
            )
        )
        assert called_name[0] == "Apple Inc"

    def test_parse_record_full(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        record = {
            "id": "HWUPKR0MPOU8FGXBT394",
            "attributes": {
                "entity": {
                    "legalName": {"name": "Apple Inc."},
                    "legalAddress": {"country": "US"},
                    "status": "ACTIVE",
                },
                "registration": {
                    "status": "ISSUED",
                    "managingLou": "EVK05KS7XY1DEII3R011",
                    "initialRegistrationDate": "2012-06-06T15:53:00.000Z",
                    "lastUpdateDate": "2024-01-15T09:00:00.000Z",
                },
            },
        }
        result = src._parse_record(record, "Apple Inc")
        assert result.lei == "HWUPKR0MPOU8FGXBT394"
        assert result.legal_name == "Apple Inc."
        assert result.jurisdiction == "US"
        assert result.entity_status == "ACTIVE"
        assert result.details["registration_status"] == "ISSUED"

    def test_api_response_no_records(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = src._query_by_name("Nonexistent Corp XYZ")

        assert result.lei == ""
        assert "No LEI records" in result.details.get("message", "")


# ===========================================================================
# Integration
# ===========================================================================


@pytest.mark.integration
class TestIntlGleifIntegration:
    def test_query_by_name(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                extra={"name": "Apple Inc"},
            )
        )
        assert isinstance(result.search_term, str)

    def test_query_by_lei(self):
        from openquery.sources.intl.gleif import IntlGleifSource

        src = IntlGleifSource()
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="HWUPKR0MPOU8FGXBT394",
            )
        )
        assert isinstance(result.lei, str)
