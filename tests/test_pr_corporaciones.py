"""Unit tests for pr.corporaciones source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pr.corporaciones import CorporacionesResult
from openquery.sources.pr.corporaciones import CorporacionesSource


class TestCorporacionesResult:
    """Test CorporacionesResult model."""

    def test_default_values(self):
        data = CorporacionesResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.entity_type == ""
        assert data.status == ""
        assert data.registration_date == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CorporacionesResult(
            search_term="EMPRESA ABC",
            entity_name="EMPRESA ABC INC",
            entity_type="Corporation",
            status="Active",
            registration_date="2010-05-15",
            details={"Charter Number": "0123456"},
        )
        json_str = data.model_dump_json()
        restored = CorporacionesResult.model_validate_json(json_str)
        assert restored.entity_name == "EMPRESA ABC INC"
        assert restored.entity_type == "Corporation"
        assert restored.status == "Active"
        assert restored.registration_date == "2010-05-15"
        assert restored.details == {"Charter Number": "0123456"}

    def test_audit_excluded_from_json(self):
        data = CorporacionesResult(search_term="test", audit=object())
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestCorporacionesSourceMeta:
    """Test CorporacionesSource metadata."""

    def test_meta_name(self):
        source = CorporacionesSource()
        meta = source.meta()
        assert meta.name == "pr.corporaciones"

    def test_meta_country(self):
        source = CorporacionesSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = CorporacionesSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = CorporacionesSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_default_timeout(self):
        source = CorporacionesSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CorporacionesSource(timeout=45.0)
        assert source._timeout == 45.0


class TestParseResult:
    """Test result parsing logic."""

    def test_parse_entity_fields(self):
        source = CorporacionesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Entity Name: EMPRESA ABC INC\n"
            "Entity Type: Corporation\n"
            "Status: Active\n"
            "Registration Date: 2010-05-15\n"
        )

        result = source._parse_result(mock_page, "EMPRESA ABC")

        assert result.entity_name == "EMPRESA ABC INC"
        assert result.entity_type == "Corporation"
        assert result.status == "Active"
        assert result.registration_date == "2010-05-15"

    def test_parse_spanish_fields(self):
        source = CorporacionesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: CORPORACION XYZ INC\n"
            "Tipo: Corporación sin fines de lucro\n"
            "Estado: Activa\n"
            "Fecha: 2015-03-20\n"
        )

        result = source._parse_result(mock_page, "XYZ")

        assert result.entity_name == "CORPORACION XYZ INC"
        assert result.entity_type == "Corporación sin fines de lucro"
        assert result.status == "Activa"
        assert result.registration_date == "2015-03-20"

    def test_parse_empty_page(self):
        source = CorporacionesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        result = source._parse_result(mock_page, "EMPRESA TEST")

        assert result.search_term == "EMPRESA TEST"
        assert result.entity_name == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        source = CorporacionesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Charter Number: 0123456\n"
            "Resident Agent: JOHN DOE\n"
        )

        result = source._parse_result(mock_page, "test")

        assert "Charter Number" in result.details
        assert result.details["Charter Number"] == "0123456"
