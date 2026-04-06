"""Unit tests for intl.basel_aml — Basel AML Index."""

from __future__ import annotations

from openquery.models.intl.basel_aml import BaselAmlResult
from openquery.sources.intl.basel_aml import BaselAmlSource


class TestBaselAmlResult:
    def test_default_values(self):
        data = BaselAmlResult()
        assert data.country == ""
        assert data.aml_score == 0.0
        assert data.aml_rank == 0
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = BaselAmlResult(
            country="Colombia",
            aml_score=5.23,
            aml_rank=42,
        )
        restored = BaselAmlResult.model_validate_json(data.model_dump_json())
        assert restored.country == "Colombia"
        assert restored.aml_score == 5.23
        assert restored.aml_rank == 42

    def test_audit_excluded_from_json(self):
        data = BaselAmlResult(country="CO", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestBaselAmlSourceMeta:
    def test_meta_name(self):
        assert BaselAmlSource().meta().name == "intl.basel_aml"

    def test_meta_country(self):
        assert BaselAmlSource().meta().country == "INTL"

    def test_meta_requires_browser(self):
        assert BaselAmlSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert BaselAmlSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert BaselAmlSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert BaselAmlSource()._timeout == 30.0


class TestParseResponse:
    def test_parse_country_by_name(self):
        source = BaselAmlSource()
        data = [
            {"country": "Colombia", "iso": "CO", "score": 5.23, "rank": 42},
            {"country": "Venezuela", "iso": "VE", "score": 7.11, "rank": 15},
        ]
        result = source._parse_response("Colombia", data)
        assert result.aml_score == 5.23
        assert result.aml_rank == 42

    def test_parse_country_by_code(self):
        source = BaselAmlSource()
        data = [{"country": "Colombia", "iso": "co", "score": 5.23, "rank": 42}]
        result = source._parse_response("co", data)
        assert result.aml_score == 5.23

    def test_parse_not_found(self):
        source = BaselAmlSource()
        data = [{"country": "Brazil", "iso": "BR", "score": 4.0, "rank": 55}]
        result = source._parse_response("ZZZZZ", data)
        assert result.aml_score == 0.0
        assert result.aml_rank == 0

    def test_parse_empty_list(self):
        source = BaselAmlSource()
        result = source._parse_response("Colombia", [])
        assert result.country == "Colombia"
        assert result.aml_score == 0.0
