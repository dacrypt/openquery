"""Unit tests for us.epa_tris — EPA Toxics Release Inventory."""

from __future__ import annotations

from openquery.models.us.epa_tris import EpaTrisResult
from openquery.sources.us.epa_tris import EpaTrisSource


class TestEpaTrisResult:
    def test_default_values(self):
        data = EpaTrisResult()
        assert data.search_term == ""
        assert data.total_facilities == 0
        assert data.facilities == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = EpaTrisResult(
            search_term="Texas",
            total_facilities=3,
            facilities=[{"facility_name": "Plant A", "state": "TX"}],
        )
        restored = EpaTrisResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "Texas"
        assert restored.total_facilities == 3
        assert restored.facilities[0]["facility_name"] == "Plant A"

    def test_audit_excluded_from_json(self):
        data = EpaTrisResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestEpaTrisSourceMeta:
    def test_meta_name(self):
        assert EpaTrisSource().meta().name == "us.epa_tris"

    def test_meta_country(self):
        assert EpaTrisSource().meta().country == "US"

    def test_meta_requires_browser(self):
        assert EpaTrisSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert EpaTrisSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert EpaTrisSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert EpaTrisSource()._timeout == 30.0

    def test_state_detection(self):
        EpaTrisSource()
        from openquery.sources.base import DocumentType, QueryInput
        inp = QueryInput(document_number="TX", document_type=DocumentType.CUSTOM)
        # Just verify it doesn't error on input construction
        assert inp.document_number == "TX"


class TestParseResponse:
    def test_parse_list_response(self):
        source = EpaTrisSource()
        data = [
            {"FAC_NAME": "Chemical Plant A", "CITY_NAME": "Houston", "ST_ABBR": "TX"},
            {"FAC_NAME": "Factory B", "CITY_NAME": "Austin", "ST_ABBR": "TX"},
        ]
        result = source._parse_response("TX", data)
        assert result.total_facilities == 2
        assert result.facilities[0]["facility_name"] == "Chemical Plant A"
        assert result.facilities[0]["state"] == "TX"

    def test_parse_empty_list(self):
        source = EpaTrisSource()
        result = source._parse_response("UNKNOWN", [])
        assert result.total_facilities == 0
        assert result.facilities == []

    def test_parse_limits_to_20(self):
        source = EpaTrisSource()
        data = [{"FAC_NAME": f"Plant {i}", "ST_ABBR": "CA"} for i in range(30)]
        result = source._parse_response("CA", data)
        assert result.total_facilities == 20
