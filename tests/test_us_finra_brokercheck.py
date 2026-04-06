"""Unit tests for us.finra_brokercheck — FINRA BrokerCheck."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.finra_brokercheck import FinraBrokercheckResult
from openquery.sources.us.finra_brokercheck import FinraBrokercheckSource


class TestFinraBrokercheckResult:
    def test_default_values(self):
        data = FinraBrokercheckResult()
        assert data.search_term == ""
        assert data.broker_name == ""
        assert data.crd_number == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = FinraBrokercheckResult(
            search_term="John Smith",
            broker_name="John Smith",
            crd_number="1234567",
            status="Registered",
        )
        restored = FinraBrokercheckResult.model_validate_json(data.model_dump_json())
        assert restored.broker_name == "John Smith"
        assert restored.crd_number == "1234567"
        assert restored.status == "Registered"

    def test_audit_excluded_from_json(self):
        data = FinraBrokercheckResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestFinraBrokercheckSourceMeta:
    def test_meta_name(self):
        assert FinraBrokercheckSource().meta().name == "us.finra_brokercheck"

    def test_meta_country(self):
        assert FinraBrokercheckSource().meta().country == "US"

    def test_meta_requires_browser(self):
        assert FinraBrokercheckSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert FinraBrokercheckSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert FinraBrokercheckSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert FinraBrokercheckSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_crd_number(self):
        source = FinraBrokercheckSource()
        page = self._make_page("CRD #1234567\nRegistered Investment Advisor\n")
        result = source._parse_result(page, "John Smith")
        assert result.crd_number == "1234567"

    def test_parse_registered_status(self):
        source = FinraBrokercheckSource()
        page = self._make_page("John Smith is currently registered.\nCRD #999\n")
        result = source._parse_result(page, "John Smith")
        assert result.status == "Registered"

    def test_parse_not_registered_status(self):
        source = FinraBrokercheckSource()
        page = self._make_page("This individual is not registered with FINRA.\n")
        result = source._parse_result(page, "Jane Doe")
        assert result.status == "Not Registered"

    def test_parse_preserves_search_term(self):
        source = FinraBrokercheckSource()
        page = self._make_page("No results found.")
        result = source._parse_result(page, "Unknown Broker")
        assert result.search_term == "Unknown Broker"
