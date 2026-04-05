"""Unit tests for NICB VINCheck source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.us.nicb_vincheck import NicbVincheckResult
from openquery.sources.us.nicb_vincheck import NicbVincheckSource


class TestNicbVincheckResult:
    """Test NicbVincheckResult model."""

    def test_default_values(self):
        data = NicbVincheckResult()
        assert data.vin == ""
        assert data.theft_records_found is False
        assert data.salvage_records_found is False
        assert data.status_message == ""
        assert data.details == []
        assert data.audit is None

    def test_round_trip_json(self):
        data = NicbVincheckResult(
            vin="1HGCM82633A004352",
            theft_records_found=False,
            salvage_records_found=True,
            status_message="Salvage record found",
            details=["No theft records found", "Salvage record found"],
        )
        json_str = data.model_dump_json()
        restored = NicbVincheckResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.theft_records_found is False
        assert restored.salvage_records_found is True
        assert restored.status_message == "Salvage record found"
        assert len(restored.details) == 2

    def test_audit_excluded_from_json(self):
        data = NicbVincheckResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_theft_found(self):
        data = NicbVincheckResult(
            vin="1HGCM82633A004352",
            theft_records_found=True,
            details=["Theft record found"],
        )
        assert data.theft_records_found is True
        assert data.salvage_records_found is False


class TestNicbVincheckSourceMeta:
    """Test NicbVincheckSource metadata."""

    def test_meta_name(self):
        source = NicbVincheckSource()
        meta = source.meta()
        assert meta.name == "us.nicb_vincheck"

    def test_meta_country(self):
        source = NicbVincheckSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = NicbVincheckSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = NicbVincheckSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 5

    def test_meta_requires_browser(self):
        source = NicbVincheckSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = NicbVincheckSource()
        meta = source.meta()
        assert meta.requires_captcha is True

    def test_default_timeout(self):
        source = NicbVincheckSource()
        assert source._timeout == 60.0

    def test_custom_timeout(self):
        source = NicbVincheckSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with API data dicts."""

    def _make_page(self, body_text: str = "") -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_no_theft_no_salvage(self):
        source = NicbVincheckSource()
        api_data = {"result": {"theft": False, "totalloss": False, "totalloss_items": []}}
        result = source._parse_results("1HGCM82633A004352", api_data, self._make_page())
        assert result.vin == "1HGCM82633A004352"
        assert result.theft_records_found is False
        assert result.salvage_records_found is False

    def test_parse_theft_found(self):
        source = NicbVincheckSource()
        api_data = {"result": {"theft": True, "totalloss": False, "totalloss_items": []}}
        result = source._parse_results("1HGCM82633A004352", api_data, self._make_page())
        assert result.theft_records_found is True
        assert result.salvage_records_found is False

    def test_parse_salvage_found(self):
        source = NicbVincheckSource()
        api_data = {
            "result": {
                "theft": False,
                "totalloss": True,
                "totalloss_items": [{"date": "2022-01-15", "cause": "Collision"}],
            }
        }
        result = source._parse_results("1HGCM82633A004352", api_data, self._make_page())
        assert result.theft_records_found is False
        assert result.salvage_records_found is True

    def test_parse_both_found(self):
        source = NicbVincheckSource()
        api_data = {"result": {"theft": True, "totalloss": True, "totalloss_items": []}}
        result = source._parse_results("1HGCM82633A004352", api_data, self._make_page())
        assert result.theft_records_found is True
        assert result.salvage_records_found is True

    def test_parse_vin_preserved(self):
        source = NicbVincheckSource()
        api_data = {"result": {"theft": False, "totalloss": False, "totalloss_items": []}}
        result = source._parse_results("TESTVIN123", api_data, self._make_page())
        assert result.vin == "TESTVIN123"

    def test_parse_fallback_no_api_data(self):
        """When api_data is empty, fall back to page body text."""
        source = NicbVincheckSource()
        page = self._make_page("VIN has not been identified as a vehicle listed")
        result = source._parse_results("TESTVIN123", {}, page)
        assert result.theft_records_found is False
        assert result.salvage_records_found is False

    def test_parse_details_populated(self):
        source = NicbVincheckSource()
        api_data = {"result": {"theft": False, "totalloss": False, "totalloss_items": []}}
        result = source._parse_results("1HGCM82633A004352", api_data, self._make_page())
        assert len(result.details) == 2
        assert any("no theft" in d.lower() for d in result.details)
