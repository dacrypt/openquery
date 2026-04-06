"""Unit tests for us.cpsc_recalls — CPSC product safety recalls."""

from __future__ import annotations

from openquery.models.us.cpsc_recalls import CpscRecallEntry, CpscRecallsResult
from openquery.sources.us.cpsc_recalls import CpscRecallsSource


class TestCpscRecallsResult:
    def test_default_values(self):
        data = CpscRecallsResult()
        assert data.search_term == ""
        assert data.total == 0
        assert data.recalls == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CpscRecallsResult(
            search_term="bicycle",
            total=2,
            recalls=[
                CpscRecallEntry(title="Bike Recall", description="Risk of injury", date="20240101"),
            ],
        )
        restored = CpscRecallsResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "bicycle"
        assert restored.total == 2
        assert len(restored.recalls) == 1
        assert restored.recalls[0].title == "Bike Recall"

    def test_audit_excluded_from_json(self):
        data = CpscRecallsResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()

    def test_recall_entry_defaults(self):
        entry = CpscRecallEntry()
        assert entry.title == ""
        assert entry.description == ""
        assert entry.date == ""


class TestCpscRecallsSourceMeta:
    def test_meta_name(self):
        assert CpscRecallsSource().meta().name == "us.cpsc_recalls"

    def test_meta_country(self):
        assert CpscRecallsSource().meta().country == "US"

    def test_meta_requires_browser(self):
        assert CpscRecallsSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert CpscRecallsSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert CpscRecallsSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert CpscRecallsSource()._timeout == 30.0


class TestParseResponse:
    def test_parse_list_response(self):
        source = CpscRecallsSource()
        data = [
            {"Title": "Toy Recall", "Description": "Choking hazard", "RecallDate": "20240315"},
            {"Title": "Toy Recall 2", "Description": "Lead paint", "RecallDate": "20240401"},
        ]
        result = source._parse_response("toy", data)
        assert result.search_term == "toy"
        assert result.total == 2
        assert result.recalls[0].title == "Toy Recall"
        assert result.recalls[1].description == "Lead paint"

    def test_parse_empty_list(self):
        source = CpscRecallsSource()
        result = source._parse_response("unknown", [])
        assert result.total == 0
        assert result.recalls == []

    def test_parse_truncates_long_fields(self):
        source = CpscRecallsSource()
        data = [{"Title": "T" * 300, "Description": "D" * 400, "RecallDate": "20240101"}]
        result = source._parse_response("test", data)
        assert len(result.recalls[0].title) <= 200
        assert len(result.recalls[0].description) <= 300
