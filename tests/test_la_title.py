"""Unit tests for Louisiana OMV title verification source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.la_title import LaTitleResult
from openquery.sources.us.la_title import LaTitleSource


class TestLaTitleResult:
    """Test LaTitleResult model."""

    def test_default_values(self):
        data = LaTitleResult()
        assert data.search_value == ""
        assert data.search_type == ""
        assert data.title_valid is False
        assert data.status_message == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = LaTitleResult(
            search_value="1HGCM82633A004352",
            search_type="vin",
            title_valid=True,
            status_message="Title is valid",
            vehicle_description="2003 HONDA ACCORD",
            details={"status": "valid"},
        )
        json_str = data.model_dump_json()
        restored = LaTitleResult.model_validate_json(json_str)
        assert restored.search_value == "1HGCM82633A004352"
        assert restored.search_type == "vin"
        assert restored.title_valid is True
        assert restored.status_message == "Title is valid"
        assert restored.vehicle_description == "2003 HONDA ACCORD"
        assert restored.details == {"status": "valid"}

    def test_audit_excluded_from_json(self):
        data = LaTitleResult(search_value="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_title_number_search_type(self):
        data = LaTitleResult(
            search_value="LA123456789",
            search_type="title_number",
            title_valid=False,
        )
        assert data.search_type == "title_number"
        assert data.title_valid is False


class TestLaTitleSourceMeta:
    """Test LaTitleSource metadata."""

    def test_meta_name(self):
        source = LaTitleSource()
        meta = source.meta()
        assert meta.name == "us.la_title"

    def test_meta_country(self):
        source = LaTitleSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = LaTitleSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = LaTitleSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = LaTitleSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = LaTitleSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = LaTitleSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = LaTitleSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, heading: str = "", vehicle: str = "") -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text

        def query_selector_side_effect(selector):
            if vehicle and "vehicle" in selector:
                el = MagicMock()
                el.inner_text.return_value = vehicle
                return el
            if heading:
                el = MagicMock()
                el.inner_text.return_value = heading
                return el
            return None

        mock_page.query_selector.side_effect = query_selector_side_effect
        return mock_page

    def test_parse_valid_title(self):
        source = LaTitleSource()
        page = self._make_page(
            "Title Verification\nTitle is valid for this vehicle.\n",
            heading="Title is valid",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.search_value == "1HGCM82633A004352"
        assert result.search_type == "vin"
        assert result.title_valid is True
        assert result.details.get("status") == "valid"

    def test_parse_title_not_found(self):
        source = LaTitleSource()
        page = self._make_page(
            "Title Verification\nNo title found for the provided VIN.\n",
            heading="No record found",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.title_valid is False
        assert result.details.get("status") == "not_found"

    def test_parse_title_number_search(self):
        source = LaTitleSource()
        page = self._make_page(
            "Title Verification\nTitle is valid.\n",
            heading="Title is valid",
        )
        result = source._parse_results(page, "LA123456789", "title_number")
        assert result.search_value == "LA123456789"
        assert result.search_type == "title_number"
        assert result.title_valid is True

    def test_parse_invalid_title(self):
        source = LaTitleSource()
        page = self._make_page(
            "Title Verification\nTitle is not valid. No record found.\n",
            heading="Invalid title",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.title_valid is False

    def test_parse_search_value_preserved(self):
        source = LaTitleSource()
        page = self._make_page("No records found.")
        result = source._parse_results(page, "TESTVIN123", "vin")
        assert result.search_value == "TESTVIN123"
        assert result.search_type == "vin"
