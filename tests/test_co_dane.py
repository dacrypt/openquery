"""Unit tests for co.dane — DANE statistics API."""

from __future__ import annotations

from openquery.models.co.dane import DaneResult
from openquery.sources.co.dane import DaneSource


class TestDaneResult:
    def test_default_values(self):
        data = DaneResult()
        assert data.indicator == ""
        assert data.value == ""
        assert data.period == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = DaneResult(
            indicator="pobreza",
            value="27.5",
            period="2022",
        )
        restored = DaneResult.model_validate_json(data.model_dump_json())
        assert restored.indicator == "pobreza"
        assert restored.value == "27.5"
        assert restored.period == "2022"

    def test_audit_excluded_from_json(self):
        data = DaneResult(indicator="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()


class TestDaneSourceMeta:
    def test_meta_name(self):
        assert DaneSource().meta().name == "co.dane"

    def test_meta_country(self):
        assert DaneSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        assert DaneSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert DaneSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert DaneSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert DaneSource()._timeout == 30.0


class TestParseResponse:
    def test_parse_list_response(self):
        source = DaneSource()
        data = [{"valor": "27.5", "periodo": "2022", "indicador": "pobreza"}]
        result = source._parse_response("pobreza", data)
        assert result.indicator == "pobreza"
        assert result.value == "27.5"
        assert result.period == "2022"

    def test_parse_empty_list(self):
        source = DaneSource()
        result = source._parse_response("unknown", [])
        assert result.indicator == "unknown"
        assert result.value == ""
        assert result.period == ""

    def test_parse_preserves_indicator(self):
        source = DaneSource()
        result = source._parse_response("desempleo", [{"value": "10.2", "year": "2023"}])
        assert result.indicator == "desempleo"
