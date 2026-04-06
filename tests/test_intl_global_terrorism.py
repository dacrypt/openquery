"""Unit tests for intl.global_terrorism — Global Terrorism Database."""

from __future__ import annotations

from openquery.models.intl.global_terrorism import GlobalTerrorismResult
from openquery.sources.intl.global_terrorism import GlobalTerrorismSource


class TestGlobalTerrorismResult:
    def test_default_values(self):
        data = GlobalTerrorismResult()
        assert data.search_term == ""
        assert data.total_incidents == 0
        assert data.incidents == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = GlobalTerrorismResult(
            search_term="Colombia",
            total_incidents=5,
            incidents=[{"country": "Colombia", "year": "2020", "incidents": 12}],
        )
        restored = GlobalTerrorismResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "Colombia"
        assert restored.total_incidents == 5
        assert restored.incidents[0]["country"] == "Colombia"

    def test_audit_excluded_from_json(self):
        data = GlobalTerrorismResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestGlobalTerrorismSourceMeta:
    def test_meta_name(self):
        assert GlobalTerrorismSource().meta().name == "intl.global_terrorism"

    def test_meta_country(self):
        assert GlobalTerrorismSource().meta().country == "INTL"

    def test_meta_requires_browser(self):
        assert GlobalTerrorismSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert GlobalTerrorismSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert GlobalTerrorismSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert GlobalTerrorismSource()._timeout == 30.0


class TestParseResponse:
    def test_parse_list_response(self):
        source = GlobalTerrorismSource()
        data = [
            {"country": "Colombia", "year": 2020, "incidents": 15},
            {"country": "Colombia", "year": 2021, "incidents": 10},
        ]
        result = source._parse_response("Colombia", data)
        assert result.total_incidents == 2
        assert result.incidents[0]["country"] == "Colombia"
        assert result.incidents[0]["year"] == "2020"

    def test_parse_empty_list(self):
        source = GlobalTerrorismSource()
        result = source._parse_response("unknown", [])
        assert result.total_incidents == 0
        assert result.incidents == []

    def test_parse_limits_to_20(self):
        source = GlobalTerrorismSource()
        data = [{"country": "X", "year": i, "incidents": 1} for i in range(30)]
        result = source._parse_response("X", data)
        assert result.total_incidents == 20
