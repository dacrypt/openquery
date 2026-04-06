"""Unit tests for pr.crim source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pr.crim import CrimResult
from openquery.sources.pr.crim import CrimSource


class TestCrimResult:
    """Test CrimResult model."""

    def test_default_values(self):
        data = CrimResult()
        assert data.account_number == ""
        assert data.property_value == ""
        assert data.tax_status == ""
        assert data.owner == ""
        assert data.address == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = CrimResult(
            account_number="123-456-789-00",
            property_value="$250,000",
            tax_status="Al día",
            owner="JUAN PEREZ",
            address="123 Calle Principal, San Juan, PR 00901",
            details={"Municipio": "San Juan"},
        )
        json_str = data.model_dump_json()
        restored = CrimResult.model_validate_json(json_str)
        assert restored.account_number == "123-456-789-00"
        assert restored.owner == "JUAN PEREZ"
        assert restored.tax_status == "Al día"
        assert restored.details == {"Municipio": "San Juan"}

    def test_audit_excluded_from_json(self):
        data = CrimResult(account_number="123", audit=object())
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestCrimSourceMeta:
    """Test CrimSource metadata."""

    def test_meta_name(self):
        source = CrimSource()
        meta = source.meta()
        assert meta.name == "pr.crim"

    def test_meta_country(self):
        source = CrimSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = CrimSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = CrimSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_default_timeout(self):
        source = CrimSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = CrimSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test result parsing logic."""

    def test_parse_owner_and_status(self):
        source = CrimSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Propietario: JUAN PEREZ\n"
            "Estado: Al día\n"
            "Valor: $250,000\n"
            "Dirección: 123 Calle Principal\n"
        )

        result = source._parse_result(mock_page, "123-456-789-00")

        assert result.account_number == "123-456-789-00"
        assert result.owner == "JUAN PEREZ"
        assert result.tax_status == "Al día"
        assert result.property_value == "$250,000"
        assert result.address == "123 Calle Principal"

    def test_parse_empty_page(self):
        source = CrimSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        result = source._parse_result(mock_page, "000-000-000-00")

        assert result.account_number == "000-000-000-00"
        assert result.owner == ""
        assert result.details == {}

    def test_parse_details_collected(self):
        source = CrimSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Municipio: San Juan\n"
            "Código Postal: 00901\n"
        )

        result = source._parse_result(mock_page, "123")

        assert "Municipio" in result.details
        assert result.details["Municipio"] == "San Juan"
