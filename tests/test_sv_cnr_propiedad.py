"""Unit tests for El Salvador CNR property registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.sv.cnr_propiedad import CnrPropiedadResult
from openquery.sources.sv.cnr_propiedad import CnrPropiedadSource


class TestCnrPropiedadResult:
    """Test CnrPropiedadResult model."""

    def test_default_values(self):
        data = CnrPropiedadResult()
        assert data.search_value == ""
        assert data.owner == ""
        assert data.property_status == ""
        assert data.liens == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CnrPropiedadResult(
            search_value="0101-0001-000",
            owner="JOSE MARTINEZ",
            property_status="INSCRITO",
            liens="SIN GRAVAMENES",
        )
        json_str = data.model_dump_json()
        restored = CnrPropiedadResult.model_validate_json(json_str)
        assert restored.search_value == "0101-0001-000"
        assert restored.owner == "JOSE MARTINEZ"
        assert restored.property_status == "INSCRITO"
        assert restored.liens == "SIN GRAVAMENES"

    def test_audit_excluded_from_json(self):
        data = CnrPropiedadResult(search_value="0101-0001-000", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestCnrPropiedadSourceMeta:
    """Test CnrPropiedadSource metadata."""

    def test_meta_name(self):
        source = CnrPropiedadSource()
        assert source.meta().name == "sv.cnr_propiedad"

    def test_meta_country(self):
        source = CnrPropiedadSource()
        assert source.meta().country == "SV"

    def test_meta_requires_browser(self):
        source = CnrPropiedadSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = CnrPropiedadSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = CnrPropiedadSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = CnrPropiedadSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CnrPropiedadSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType
        source = CnrPropiedadSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test CnrPropiedadSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = CnrPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "CARLOS LOPEZ"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "INSCRITO"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "SIN GRAVAMENES"
        mock_row1.query_selector_all.return_value = [cell0, cell1, cell2]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "0101-0001-000")
        assert result.search_value == "0101-0001-000"
        assert result.owner == "CARLOS LOPEZ"
        assert result.property_status == "INSCRITO"
        assert result.liens == "SIN GRAVAMENES"

    def test_parse_empty_page(self):
        source = CnrPropiedadSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "9999-9999-999")
        assert result.search_value == "9999-9999-999"
        assert result.owner == ""
