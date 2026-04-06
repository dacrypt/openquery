"""Unit tests for Florida DHSMV vehicle check source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.fl_dmv import FlDmvResult
from openquery.sources.us.fl_dmv import FlDmvSource


class TestFlDmvResult:
    """Test FlDmvResult model."""

    def test_default_values(self):
        data = FlDmvResult()
        assert data.search_type == ""
        assert data.search_value == ""
        assert data.title_status == ""
        assert data.brand_history == []
        assert data.odometer == ""
        assert data.registration_status == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = FlDmvResult(
            search_type="vin",
            search_value="1HGCM82633A004352",
            title_status="Clean",
            brand_history=["Salvage", "Rebuilt"],
            odometer="52000 miles",
            registration_status="Active",
            vehicle_description="2003 Honda Accord",
            details={"title_status_raw": "Title Status: Clean"},
        )
        json_str = data.model_dump_json()
        restored = FlDmvResult.model_validate_json(json_str)
        assert restored.search_type == "vin"
        assert restored.search_value == "1HGCM82633A004352"
        assert restored.title_status == "Clean"
        assert restored.brand_history == ["Salvage", "Rebuilt"]
        assert restored.odometer == "52000 miles"
        assert restored.registration_status == "Active"
        assert restored.vehicle_description == "2003 Honda Accord"
        assert restored.details == {"title_status_raw": "Title Status: Clean"}

    def test_audit_excluded_from_json(self):
        data = FlDmvResult(search_value="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_brand_history_defaults_empty(self):
        data = FlDmvResult()
        assert isinstance(data.brand_history, list)
        assert len(data.brand_history) == 0

    def test_details_defaults_empty_dict(self):
        data = FlDmvResult()
        assert isinstance(data.details, dict)
        assert len(data.details) == 0


class TestFlDmvSourceMeta:
    """Test FlDmvSource metadata."""

    def test_meta_name(self):
        source = FlDmvSource()
        meta = source.meta()
        assert meta.name == "us.fl_dmv"

    def test_meta_country(self):
        source = FlDmvSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = FlDmvSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs
        assert DocumentType.PLATE in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = FlDmvSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = FlDmvSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = FlDmvSource()
        meta = source.meta()
        assert meta.requires_captcha is True

    def test_default_timeout(self):
        source = FlDmvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = FlDmvSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, heading: str = "") -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if heading:
            mock_el = MagicMock()
            mock_el.inner_text.return_value = heading
            mock_page.query_selector.return_value = mock_el
        else:
            mock_page.query_selector.return_value = None
        return mock_page

    def test_parse_clean_title(self):
        source = FlDmvSource()
        page = self._make_page(
            "Vehicle Title Check\n"
            "Title Status: Clean — no brands recorded.\n"
            "Registration Status: Active\n",
            heading="2003 Honda Accord",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.search_value == "1HGCM82633A004352"
        assert result.search_type == "vin"
        assert "title status" in result.title_status.lower()
        assert result.brand_history == []
        assert result.vehicle_description == "2003 Honda Accord"

    def test_parse_salvage_brand(self):
        source = FlDmvSource()
        page = self._make_page(
            "Vehicle Title Check\n"
            "Title Status: Branded\n"
            "Brand History: Salvage, Rebuilt\n"
            "Odometer: 75000 miles\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert "Salvage" in result.brand_history
        assert "Rebuilt" in result.brand_history

    def test_parse_plate_search_type(self):
        source = FlDmvSource()
        page = self._make_page(
            "Vehicle Title Check\nRegistration Status: Active\n",
        )
        result = source._parse_results(page, "ABC123", "plate")
        assert result.search_type == "plate"
        assert result.search_value == "ABC123"

    def test_parse_odometer_captured(self):
        source = FlDmvSource()
        page = self._make_page(
            "Odometer: 52000 miles\nTitle Status: Clean\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert "odometer" in result.odometer.lower()

    def test_parse_registration_status(self):
        source = FlDmvSource()
        page = self._make_page(
            "Title Status: Clean\nRegistration Status: Expired\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert "registration" in result.registration_status.lower()

    def test_parse_flood_brand(self):
        source = FlDmvSource()
        page = self._make_page(
            "Title Status: Branded\nBrand History: Flood damage reported\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert "Flood" in result.brand_history

    def test_parse_no_brands_empty_list(self):
        source = FlDmvSource()
        page = self._make_page(
            "Title Status: Clean\nNo brand history on record.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352", "vin")
        assert result.brand_history == []

    def test_parse_value_always_preserved(self):
        source = FlDmvSource()
        page = self._make_page("No records found.")
        result = source._parse_results(page, "TESTVIN999", "vin")
        assert result.search_value == "TESTVIN999"
