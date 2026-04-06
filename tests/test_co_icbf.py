"""Unit tests for co.icbf — ICBF child welfare checks."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.icbf import IcbfResult
from openquery.sources.co.icbf import IcbfSource


class TestIcbfResult:
    def test_default_values(self):
        data = IcbfResult()
        assert data.search_term == ""
        assert data.total_records == 0
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IcbfResult(search_term="García", total_records=3)
        restored = IcbfResult.model_validate_json(data.model_dump_json())
        assert restored.search_term == "García"
        assert restored.total_records == 3

    def test_audit_excluded_from_json(self):
        data = IcbfResult(search_term="TEST", audit={"pdf": "bytes"})
        assert "audit" not in data.model_dump_json()
        assert data.audit == {"pdf": "bytes"}


class TestIcbfSourceMeta:
    def test_meta_name(self):
        assert IcbfSource().meta().name == "co.icbf"

    def test_meta_country(self):
        assert IcbfSource().meta().country == "CO"

    def test_meta_requires_browser(self):
        assert IcbfSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        assert IcbfSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert IcbfSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert IcbfSource()._timeout == 30.0


class TestParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_preserves_search_term(self):
        source = IcbfSource()
        page = self._make_page("García García\nGarcía López\n")
        result = source._parse_result(page, "García")
        assert result.search_term == "García"

    def test_parse_counts_matches(self):
        source = IcbfSource()
        page = self._make_page("García García\nGarcía López\nOtro nombre\n")
        result = source._parse_result(page, "García")
        assert result.total_records >= 2

    def test_parse_empty(self):
        source = IcbfSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "NOMATCH")
        assert result.total_records == 0
