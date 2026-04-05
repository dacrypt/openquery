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
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = NicbVincheckSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = NicbVincheckSource(timeout=60.0)
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

    def test_parse_no_theft_no_salvage(self):
        source = NicbVincheckSource()
        page = self._make_page(
            "VINCheck Results\n"
            "No theft record found for this VIN.\n"
            "No salvage record found for this VIN.\n",
            heading="No records found",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.vin == "1HGCM82633A004352"
        assert result.theft_records_found is False
        assert result.salvage_records_found is False

    def test_parse_theft_found(self):
        source = NicbVincheckSource()
        page = self._make_page(
            "VINCheck Results\n"
            "A theft record has been reported for this vehicle.\n"
            "No salvage record found.\n",
            heading="Theft record found",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.theft_records_found is True
        assert result.salvage_records_found is False

    def test_parse_salvage_found(self):
        source = NicbVincheckSource()
        page = self._make_page(
            "VINCheck Results\n"
            "No theft record found.\n"
            "A salvage record has been reported for this vehicle.\n",
            heading="Salvage record found",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.theft_records_found is False
        assert result.salvage_records_found is True

    def test_parse_both_found(self):
        source = NicbVincheckSource()
        page = self._make_page(
            "VINCheck Results\n"
            "A theft record has been reported for this vehicle.\n"
            "A salvage record has been reported for this vehicle.\n",
        )
        result = source._parse_results(page, "1HGCM82633A004352")
        assert result.theft_records_found is True
        assert result.salvage_records_found is True

    def test_parse_vin_preserved(self):
        source = NicbVincheckSource()
        page = self._make_page("No records found.")
        result = source._parse_results(page, "TESTVIN123")
        assert result.vin == "TESTVIN123"
