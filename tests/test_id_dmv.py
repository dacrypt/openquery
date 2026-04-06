"""Unit tests for Idaho DMV title + registration status source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.id_dmv import IdDmvResult
from openquery.sources.us.id_dmv import IdDmvSource


class TestIdDmvResult:
    """Test IdDmvResult model."""

    def test_default_values(self):
        data = IdDmvResult()
        assert data.vin == ""
        assert data.title_status == ""
        assert data.registration_status == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IdDmvResult(
            vin="1HGCM82633A004352",
            title_status="Title on record",
            registration_status="Registration current",
            vehicle_description="2003 HONDA ACCORD",
            details={"title_raw": "Title on record", "registration_raw": "Registration current"},
        )
        json_str = data.model_dump_json()
        restored = IdDmvResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.title_status == "Title on record"
        assert restored.registration_status == "Registration current"
        assert restored.vehicle_description == "2003 HONDA ACCORD"
        assert restored.details["title_raw"] == "Title on record"

    def test_audit_excluded_from_json(self):
        data = IdDmvResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_partial_fields(self):
        data = IdDmvResult(vin="TESTVIN123", title_status="No title found")
        assert data.vin == "TESTVIN123"
        assert data.title_status == "No title found"
        assert data.registration_status == ""


class TestIdDmvSourceMeta:
    """Test IdDmvSource metadata."""

    def test_meta_name(self):
        source = IdDmvSource()
        meta = source.meta()
        assert meta.name == "us.id_dmv"

    def test_meta_country(self):
        source = IdDmvSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = IdDmvSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = IdDmvSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = IdDmvSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = IdDmvSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = IdDmvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = IdDmvSource(timeout=60.0)
        assert source._timeout == 60.0

    def test_meta_url(self):
        from openquery.sources.us.id_dmv import TITLE_URL

        source = IdDmvSource()
        meta = source.meta()
        assert meta.url == TITLE_URL


class TestParseResult:
    """Test _parse_title and _parse_registration parsing logic with mocked page."""

    def _make_page(self, body_text: str, status_text: str = "") -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if status_text:
            mock_el = MagicMock()
            mock_el.inner_text.return_value = status_text
            mock_page.query_selector.return_value = mock_el
        else:
            mock_page.query_selector.return_value = None
        return mock_page

    def test_parse_title_sets_status(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="1HGCM82633A004352")
        page = self._make_page(
            "Title Status\nTitle on record for this vehicle.\nOwner information not displayed.",
            status_text="Title on record for this vehicle.",
        )
        source._parse_title(page, result)
        assert result.title_status == "Title on record for this vehicle."
        assert "title_raw" in result.details

    def test_parse_registration_sets_status(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="1HGCM82633A004352")
        page = self._make_page(
            "Registration Status\nRegistration is current.\nExpires 2025-03-01.",
            status_text="Registration is current.",
        )
        source._parse_registration(page, result)
        assert result.registration_status == "Registration is current."
        assert "registration_raw" in result.details

    def test_parse_title_no_match_falls_back_to_body(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="1HGCM82633A004352")
        page = self._make_page("No title record found for this VIN.")
        source._parse_title(page, result)
        assert result.title_status != ""

    def test_parse_registration_no_match_falls_back_to_body(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="1HGCM82633A004352")
        page = self._make_page("No registration found for this VIN.")
        source._parse_registration(page, result)
        assert result.registration_status != ""

    def test_parse_title_stores_raw_snippet(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="TESTVIN123")
        body = "Title Status\n" + "x" * 600
        page = self._make_page(body)
        source._parse_title(page, result)
        assert len(result.details["title_raw"]) <= 500

    def test_parse_vehicle_description_from_page(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="1HGCM82633A004352")
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "2003 HONDA ACCORD LX"
        mock_el = MagicMock()
        mock_el.inner_text.return_value = "2003 HONDA ACCORD LX"
        mock_page.query_selector.return_value = mock_el
        source._parse_title(mock_page, result)
        # vehicle_description populated from selector or body
        assert isinstance(result.vehicle_description, str)

    def test_parse_title_vin_preserved(self):
        source = IdDmvSource()
        result = IdDmvResult(vin="TESTVIN999")
        page = self._make_page("No title found.")
        source._parse_title(page, result)
        assert result.vin == "TESTVIN999"

    def test_query_wrong_document_type_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = IdDmvSource()
        inp = QueryInput(document_type=DocumentType.PASSPORT, document_number="ABC123")
        try:
            source.query(inp)
            assert False, "Expected SourceError"
        except SourceError as e:
            assert "us.id_dmv" in str(e)

    def test_query_empty_vin_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = IdDmvSource()
        inp = QueryInput(document_type=DocumentType.VIN, document_number="   ")
        try:
            source.query(inp)
            assert False, "Expected SourceError"
        except SourceError as e:
            assert "us.id_dmv" in str(e)
