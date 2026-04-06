"""Unit tests for New York DMV title/lien status source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.models.us.ny_dmv import NyDmvResult
from openquery.sources.us.ny_dmv import NyDmvSource


class TestNyDmvResult:
    """Test NyDmvResult model."""

    def test_default_values(self):
        data = NyDmvResult()
        assert data.vin == ""
        assert data.make == ""
        assert data.model_year == ""
        assert data.title_status == ""
        assert data.lien_status == ""
        assert data.vehicle_description == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = NyDmvResult(
            vin="1HGCM82633A004352",
            make="HONDA",
            model_year="2003",
            title_status="Clear",
            lien_status="No lien",
            vehicle_description="HONDA ACCORD 2003",
        )
        json_str = data.model_dump_json()
        restored = NyDmvResult.model_validate_json(json_str)
        assert restored.vin == "1HGCM82633A004352"
        assert restored.make == "HONDA"
        assert restored.model_year == "2003"
        assert restored.title_status == "Clear"
        assert restored.lien_status == "No lien"

    def test_audit_excluded_from_json(self):
        data = NyDmvResult(vin="1HGCM82633A004352", audit={"evidence": "pdf_bytes"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf_bytes"}

    def test_details_dict(self):
        data = NyDmvResult(
            vin="1HGCM82633A004352",
            details={"Title Status": "Clear", "Lien": "No"},
        )
        assert data.details["Title Status"] == "Clear"
        assert data.details["Lien"] == "No"


class TestNyDmvSourceMeta:
    """Test NyDmvSource metadata."""

    def test_meta_name(self):
        source = NyDmvSource()
        meta = source.meta()
        assert meta.name == "us.ny_dmv"

    def test_meta_country(self):
        source = NyDmvSource()
        meta = source.meta()
        assert meta.country == "US"

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = NyDmvSource()
        meta = source.meta()
        assert DocumentType.VIN in meta.supported_inputs

    def test_meta_rate_limit(self):
        source = NyDmvSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = NyDmvSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_requires_captcha(self):
        source = NyDmvSource()
        meta = source.meta()
        assert meta.requires_captcha is False

    def test_default_timeout(self):
        source = NyDmvSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = NyDmvSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_results parsing logic with mocked page."""

    def _make_page(self, body_text: str, rows: list[tuple[str, str]] | None = None) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text

        mock_rows = []
        for key, val in rows or []:
            mock_row = MagicMock()
            mock_row.evaluate.return_value = "tr"
            mock_row.inner_text.return_value = f"{key}\t{val}"
            cell_key = MagicMock()
            cell_key.inner_text.return_value = key
            cell_val = MagicMock()
            cell_val.inner_text.return_value = val
            mock_row.query_selector_all.return_value = [cell_key, cell_val]
            mock_rows.append(mock_row)

        mock_page.query_selector_all.return_value = mock_rows
        return mock_page

    def test_parse_clear_title_no_lien(self):
        source = NyDmvSource()
        page = self._make_page(
            "Title Status Results\nTitle Status: Clear\nNo lien on this vehicle.\n",
            rows=[("Title Status", "Clear"), ("Lien", "No lien")],
        )
        result = source._parse_results(page, "1HGCM82633A004352", "2003", "HONDA")
        assert result.vin == "1HGCM82633A004352"
        assert result.model_year == "2003"
        assert result.make == "HONDA"

    def test_parse_fallback_clear_from_body(self):
        source = NyDmvSource()
        page = self._make_page("Title lookup results\nStatus: clear\nNo lien recorded.\n")
        result = source._parse_results(page, "1HGCM82633A004352", "2003", "HONDA")
        assert result.title_status == "Clear"
        assert result.lien_status == "No lien"

    def test_parse_fallback_salvage_from_body(self):
        source = NyDmvSource()
        page = self._make_page("Title: salvage — vehicle declared total loss.")
        result = source._parse_results(page, "TEST123", "2010", "FORD")
        assert result.title_status == "Salvage"

    def test_parse_lien_reported_from_body(self):
        source = NyDmvSource()
        page = self._make_page("Vehicle has an active lien recorded.")
        result = source._parse_results(page, "TEST123", "2010", "FORD")
        assert result.lien_status == "Lien reported"

    def test_parse_vin_preserved(self):
        source = NyDmvSource()
        page = self._make_page("No records.")
        result = source._parse_results(page, "TESTVIN123", "2020", "TOYOTA")
        assert result.vin == "TESTVIN123"
        assert result.make == "TOYOTA"
        assert result.model_year == "2020"

    def test_query_missing_year_raises(self):
        from openquery.sources.base import DocumentType, QueryInput

        source = NyDmvSource()
        inp = QueryInput(
            document_type=DocumentType.VIN,
            document_number="1HGCM82633A004352",
            extra={"make": "HONDA"},
        )
        with pytest.raises(Exception, match="year"):
            source.query(inp)

    def test_query_missing_make_raises(self):
        from openquery.sources.base import DocumentType, QueryInput

        source = NyDmvSource()
        inp = QueryInput(
            document_type=DocumentType.VIN,
            document_number="1HGCM82633A004352",
            extra={"year": "2003"},
        )
        with pytest.raises(Exception, match="make"):
            source.query(inp)

    def test_query_wrong_document_type_raises(self):
        from openquery.sources.base import DocumentType, QueryInput

        source = NyDmvSource()
        inp = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="123456",
            extra={"year": "2003", "make": "HONDA"},
        )
        with pytest.raises(Exception):
            source.query(inp)
