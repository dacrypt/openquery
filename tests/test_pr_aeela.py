"""Tests for pr.aeela — LUMA/AEE electric utility account status."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestAeelaResult:
    """Test AeelaResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.pr.aeela import AeelaResult

        r = AeelaResult()
        assert r.account_number == ""
        assert r.account_status == ""
        assert r.balance == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pr.aeela import AeelaResult

        r = AeelaResult(account_number="1234567890", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "1234567890" in dumped

    def test_json_roundtrip(self):
        from openquery.models.pr.aeela import AeelaResult

        r = AeelaResult(
            account_number="1234567890",
            account_status="Active",
            balance="$125.50",
            details={"Status": "Active"},
        )
        r2 = AeelaResult.model_validate_json(r.model_dump_json())
        assert r2.account_number == "1234567890"
        assert r2.account_status == "Active"
        assert r2.balance == "$125.50"

    def test_queried_at_default(self):
        from openquery.models.pr.aeela import AeelaResult

        before = datetime.now()
        r = AeelaResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestAeelaSourceMeta:
    """Test pr.aeela source metadata."""

    def test_meta_name(self):
        from openquery.sources.pr.aeela import AeelaSource

        assert AeelaSource().meta().name == "pr.aeela"

    def test_meta_country(self):
        from openquery.sources.pr.aeela import AeelaSource

        assert AeelaSource().meta().country == "PR"

    def test_meta_requires_browser(self):
        from openquery.sources.pr.aeela import AeelaSource

        assert AeelaSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.pr.aeela import AeelaSource

        assert DocumentType.CUSTOM in AeelaSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pr.aeela import AeelaSource

        assert AeelaSource().meta().rate_limit_rpm == 10


class TestAeelaParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, account_number: str = "1234567890"):
        from openquery.sources.pr.aeela import AeelaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return AeelaSource()._parse_result(page, account_number)

    def test_account_number_preserved(self):
        assert self._parse("Data").account_number == "1234567890"

    def test_account_status_parsed(self):
        result = self._parse("Status: Active\nOther data")
        assert result.account_status == "Active"

    def test_balance_parsed(self):
        result = self._parse("Balance: $125.50\nOther")
        assert result.balance == "$125.50"

    def test_balance_from_dollar_sign(self):
        result = self._parse("Amount due $200.00")
        assert "$200.00" in result.balance

    def test_empty_body(self):
        result = self._parse("")
        assert result.account_number == "1234567890"
        assert result.account_status == ""

    def test_query_missing_account_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.pr.aeela import AeelaSource

        with pytest.raises(SourceError, match="[Aa]ccount"):
            AeelaSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )
