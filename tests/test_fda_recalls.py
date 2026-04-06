"""Unit tests for us.fda_recalls — FDA food/drug recall events source."""

from __future__ import annotations

from openquery.models.us.fda_recalls import FdaRecallEvent, FdaRecallsResult
from openquery.sources.us.fda_recalls import FdaRecallsSource


class TestFdaRecallsResult:
    """Test FdaRecallsResult model."""

    def test_default_values(self):
        data = FdaRecallsResult()
        assert data.search_term == ""
        assert data.total == 0
        assert data.recalls == []
        assert data.audit is None

    def test_round_trip_json(self):
        data = FdaRecallsResult(
            search_term="peanut butter",
            total=2,
            recalls=[
                FdaRecallEvent(
                    product="Peanut Butter Crackers",
                    company="Acme Foods Inc",
                    reason="Undeclared peanuts",
                    classification="Class I",
                    status="Ongoing",
                    date="20240115",
                )
            ],
        )
        json_str = data.model_dump_json()
        restored = FdaRecallsResult.model_validate_json(json_str)
        assert restored.search_term == "peanut butter"
        assert restored.total == 2
        assert len(restored.recalls) == 1
        assert restored.recalls[0].company == "Acme Foods Inc"
        assert restored.recalls[0].classification == "Class I"

    def test_audit_excluded_from_json(self):
        data = FdaRecallsResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestFdaRecallEvent:
    """Test FdaRecallEvent model."""

    def test_default_values(self):
        event = FdaRecallEvent()
        assert event.product == ""
        assert event.company == ""
        assert event.reason == ""
        assert event.classification == ""
        assert event.status == ""
        assert event.date == ""


class TestFdaRecallsSourceMeta:
    """Test FdaRecallsSource metadata."""

    def test_meta_name(self):
        source = FdaRecallsSource()
        assert source.meta().name == "us.fda_recalls"

    def test_meta_country(self):
        source = FdaRecallsSource()
        assert source.meta().country == "US"

    def test_meta_rate_limit(self):
        source = FdaRecallsSource()
        assert source.meta().rate_limit_rpm == 20

    def test_meta_requires_browser(self):
        source = FdaRecallsSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = FdaRecallsSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = FdaRecallsSource()
        assert source._timeout == 30.0


class TestParseResponse:
    """Test _parse_response parsing logic."""

    def test_parse_valid_response(self):
        source = FdaRecallsSource()
        data = {
            "meta": {"results": {"total": 2}},
            "results": [
                {
                    "product_description": "Peanut Butter Crackers 12oz",
                    "recalling_firm": "Acme Foods Inc",
                    "reason_for_recall": "Undeclared peanuts",
                    "classification": "Class I",
                    "status": "Ongoing",
                    "report_date": "20240115",
                },
                {
                    "product_description": "Peanut Butter Cookies",
                    "recalling_firm": "Beta Bakery LLC",
                    "reason_for_recall": "Possible Salmonella",
                    "classification": "Class II",
                    "status": "Terminated",
                    "report_date": "20240201",
                },
            ],
        }
        result = source._parse_response("peanut butter", data)
        assert result.search_term == "peanut butter"
        assert result.total == 2
        assert len(result.recalls) == 2
        assert result.recalls[0].company == "Acme Foods Inc"
        assert result.recalls[0].classification == "Class I"
        assert result.recalls[1].status == "Terminated"

    def test_parse_empty_results(self):
        source = FdaRecallsSource()
        data = {"meta": {"results": {"total": 0}}, "results": []}
        result = source._parse_response("nothing", data)
        assert result.total == 0
        assert result.recalls == []

    def test_parse_product_truncated(self):
        source = FdaRecallsSource()
        long_product = "A" * 300
        data = {
            "meta": {"results": {"total": 1}},
            "results": [
                {
                    "product_description": long_product,
                    "recalling_firm": "Test Co",
                    "reason_for_recall": "Test reason",
                    "classification": "Class III",
                    "status": "Ongoing",
                    "report_date": "20240101",
                }
            ],
        }
        result = source._parse_response("test", data)
        assert len(result.recalls[0].product) == 200
