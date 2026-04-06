"""Unit tests for intl.pep_check — PEP check."""

from __future__ import annotations

from openquery.models.intl.pep_check import PepCheckResult
from openquery.sources.intl.pep_check import PepCheckSource


class TestPepCheckResult:
    def test_default_values(self):
        data = PepCheckResult()
        assert data.search_term == ""
        assert data.is_pep is False
        assert data.jurisdictions == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PepCheckResult(
            search_term="John Doe",
            is_pep=True,
            jurisdictions=["US", "GB"],
        )
        restored = PepCheckResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "John Doe"
        assert restored.is_pep is True
        assert "US" in restored.jurisdictions

    def test_audit_excluded_from_json(self):
        data = PepCheckResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestPepCheckSourceMeta:
    def test_meta_name(self):
        assert PepCheckSource().meta().name == "intl.pep_check"

    def test_meta_country(self):
        assert PepCheckSource().meta().country == "INTL"

    def test_meta_requires_browser(self):
        assert PepCheckSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert PepCheckSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert PepCheckSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert PepCheckSource()._timeout == 30.0


class TestParseResponse:
    def test_parse_pep_found(self):
        source = PepCheckSource()
        data = {
            "results": [
                {
                    "datasets": ["us_ofac", "gb_fcdo"],
                    "properties": {"country": ["US", "GB"]},
                }
            ]
        }
        result = source._parse_response("Test Person", data)
        assert result.is_pep is True
        assert len(result.jurisdictions) > 0

    def test_parse_no_results(self):
        source = PepCheckSource()
        data = {"results": []}
        result = source._parse_response("Unknown Person", data)
        assert result.is_pep is False
        assert result.jurisdictions == []

    def test_parse_total_matches(self):
        source = PepCheckSource()
        data = {"results": [{"datasets": [], "properties": {}}] * 3}
        result = source._parse_response("Test", data)
        assert result.details["total_matches"] == 3
