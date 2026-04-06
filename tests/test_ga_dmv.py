"""Unit tests for Georgia DRIVES DMV source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.ga_dmv import GaDmvResult
from openquery.sources.us.ga_dmv import GaDmvSource


class TestGaDmvResult:
    """Test GaDmvResult model."""

    def test_default_values(self):
        data = GaDmvResult()
        assert data.search_type == ""
        assert data.search_value == ""
        assert data.title_status == ""
        assert data.lienholder == ""
        assert data.brand_info == ""
        assert data.insurance_status == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json_title(self):
        data = GaDmvResult(
            search_type="title",
            search_value="1HGCM82633A004352",
            title_status="valid",
            lienholder="First National Bank",
            brand_info="Clean",
            vehicle_description="2003 Honda Accord",
            details={"title_status": "Valid", "lienholder": "First National Bank"},
        )
        json_str = data.model_dump_json()
        restored = GaDmvResult.model_validate_json(json_str)
        assert restored.search_type == "title"
        assert restored.search_value == "1HGCM82633A004352"
        assert restored.title_status == "valid"
        assert restored.lienholder == "First National Bank"
        assert restored.brand_info == "Clean"
        assert restored.vehicle_description == "2003 Honda Accord"

    def test_round_trip_json_insurance(self):
        data = GaDmvResult(
            search_type="insurance",
            search_value="ABC1234",
            insurance_status="active",
            vehicle_description="2020 Toyota Camry",
            details={"insurance_status": "Active"},
        )
        json_str = data.model_dump_json()
        restored = GaDmvResult.model_validate_json(json_str)
        assert restored.search_type == "insurance"
        assert restored.search_value == "ABC1234"
        assert restored.insurance_status == "active"

    def test_audit_excluded_from_json(self):
        data = GaDmvResult(search_value="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_details_dict(self):
        data = GaDmvResult(details={"title_status": "Valid", "lienholder": "Bank A"})
        assert data.details["title_status"] == "Valid"
        assert data.details["lienholder"] == "Bank A"


class TestGaDmvSourceMeta:
    """Test GaDmvSource metadata."""

    def test_meta_name(self):
        source = GaDmvSource()
        meta = source.meta()
        assert meta.name == "us.ga_dmv"

    def test_meta_country(self):
        source = GaDmvSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = GaDmvSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs
        assert DocumentType.PLATE in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = GaDmvSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = GaDmvSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = GaDmvSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = GaDmvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = GaDmvSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_title_results and _parse_insurance_results with mocked page."""

    def _make_page(self, body_text: str, selector_map: dict | None = None) -> MagicMock:
        """Build a mock page with configurable body text and element selectors."""
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text

        def query_selector_side_effect(selector):
            if selector_map:
                for key, value in selector_map.items():
                    if key in selector:
                        mock_el = MagicMock()
                        mock_el.inner_text.return_value = value
                        return mock_el
            return None

        mock_page.query_selector.side_effect = query_selector_side_effect
        return mock_page

    def test_parse_title_valid(self):
        source = GaDmvSource()
        page = self._make_page("Title is valid for this vehicle.\nClean title.")
        result = source._parse_title_results(page, "1HGCM82633A004352")
        assert result.search_type == "title"
        assert result.search_value == "1HGCM82633A004352"
        assert result.title_status == "valid"

    def test_parse_title_not_found(self):
        source = GaDmvSource()
        page = self._make_page("No title found for this VIN.")
        result = source._parse_title_results(page, "1HGCM82633A004352")
        assert result.title_status == "not_found"

    def test_parse_title_unknown_status(self):
        source = GaDmvSource()
        page = self._make_page("An error occurred processing your request.")
        result = source._parse_title_results(page, "1HGCM82633A004352")
        assert result.title_status == ""

    def test_parse_title_preserves_vin(self):
        source = GaDmvSource()
        page = self._make_page("No record.")
        result = source._parse_title_results(page, "TESTVIN123")
        assert result.search_value == "TESTVIN123"

    def test_parse_insurance_active(self):
        source = GaDmvSource()
        page = self._make_page("Insurance is active for this vehicle.")
        result = source._parse_insurance_results(page, "ABC1234")
        assert result.search_type == "insurance"
        assert result.search_value == "ABC1234"
        assert result.insurance_status == "active"

    def test_parse_insurance_uninsured(self):
        source = GaDmvSource()
        page = self._make_page("This vehicle is uninsured.")
        result = source._parse_insurance_results(page, "ABC1234")
        assert result.insurance_status == "uninsured"

    def test_parse_insurance_unknown_status(self):
        source = GaDmvSource()
        page = self._make_page("An error occurred processing your request.")
        result = source._parse_insurance_results(page, "ABC1234")
        assert result.insurance_status == ""

    def test_parse_insurance_preserves_plate(self):
        source = GaDmvSource()
        page = self._make_page("No record.")
        result = source._parse_insurance_results(page, "XYZ9876")
        assert result.search_value == "XYZ9876"

    def test_parse_title_with_lienholder(self):
        source = GaDmvSource()
        page = self._make_page(
            "Title is valid.\nLienholder: Wells Fargo",
            selector_map={"lien": "Wells Fargo"},
        )
        result = source._parse_title_results(page, "1HGCM82633A004352")
        assert result.title_status == "valid"
        assert result.lienholder == "Wells Fargo"
        assert result.details.get("lienholder") == "Wells Fargo"

    def test_parse_title_with_brand_info(self):
        source = GaDmvSource()
        page = self._make_page(
            "Title is valid.\nBrand: Salvage",
            selector_map={"brand": "Salvage"},
        )
        result = source._parse_title_results(page, "1HGCM82633A004352")
        assert result.brand_info == "Salvage"
        assert result.details.get("brand_info") == "Salvage"
