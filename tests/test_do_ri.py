"""Unit tests for Dominican Republic Registro Inmobiliario property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.do.ri import RiResult
from openquery.sources.do.ri import RiSource


class TestRiResult:
    """Test RiResult model."""

    def test_default_values(self):
        data = RiResult()
        assert data.search_value == ""
        assert data.property_status == ""
        assert data.owner == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RiResult(
            search_value="100-0001-001",
            property_status="REGISTRADO",
            owner="JUAN PEREZ",
        )
        json_str = data.model_dump_json()
        restored = RiResult.model_validate_json(json_str)
        assert restored.search_value == "100-0001-001"
        assert restored.property_status == "REGISTRADO"
        assert restored.owner == "JUAN PEREZ"

    def test_audit_excluded_from_json(self):
        data = RiResult(search_value="100-0001-001", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRiSourceMeta:
    """Test RiSource metadata."""

    def test_meta_name(self):
        source = RiSource()
        assert source.meta().name == "do.ri"

    def test_meta_country(self):
        source = RiSource()
        assert source.meta().country == "DO"

    def test_meta_requires_browser(self):
        source = RiSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = RiSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = RiSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = RiSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = RiSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = RiSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test RiSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = RiSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "REGISTRADO"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "MARIA GARCIA"
        mock_row1.query_selector_all.return_value = [cell0, cell1]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "100-0001-001")
        assert result.search_value == "100-0001-001"
        assert result.property_status == "REGISTRADO"
        assert result.owner == "MARIA GARCIA"

    def test_parse_empty_page(self):
        source = RiSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "999-9999-999")
        assert result.search_value == "999-9999-999"
        assert result.property_status == ""
