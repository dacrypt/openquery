"""Unit tests for pr.tribunales source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.pr.tribunales import TribunalesResult
from openquery.sources.pr.tribunales import TribunalesSource


class TestTribunalesResult:
    """Test TribunalesResult model."""

    def test_default_values(self):
        data = TribunalesResult()
        assert data.search_term == ""
        assert data.case_number == ""
        assert data.court == ""
        assert data.status == ""
        assert data.parties == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = TribunalesResult(
            search_term="JUAN PEREZ",
            case_number="SJ2024CV01234",
            court="Tribunal de Primera Instancia San Juan",
            status="Activo",
            parties=["JUAN PEREZ", "EMPRESA ABC"],
            details={"Sala": "Civil"},
        )
        json_str = data.model_dump_json()
        restored = TribunalesResult.model_validate_json(json_str)
        assert restored.case_number == "SJ2024CV01234"
        assert restored.search_term == "JUAN PEREZ"
        assert len(restored.parties) == 2
        assert restored.details == {"Sala": "Civil"}

    def test_audit_excluded_from_json(self):
        data = TribunalesResult(search_term="test", audit=object())
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestTribunalesSourceMeta:
    """Test TribunalesSource metadata."""

    def test_meta_name(self):
        source = TribunalesSource()
        meta = source.meta()
        assert meta.name == "pr.tribunales"

    def test_meta_country(self):
        source = TribunalesSource()
        meta = source.meta()
        assert meta.country == "PR"

    def test_meta_rate_limit(self):
        source = TribunalesSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = TribunalesSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_default_timeout(self):
        source = TribunalesSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = TribunalesSource(timeout=45.0)
        assert source._timeout == 45.0


class TestParseResult:
    """Test result parsing logic."""

    def test_parse_case_and_court(self):
        source = TribunalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Número: SJ2024CV01234\n"
            "Tribunal: Tribunal de Primera Instancia San Juan\n"
            "Estado: Activo\n"
            "Demandante: JUAN PEREZ\n"
            "Demandado: EMPRESA ABC\n"
        )

        result = source._parse_result(mock_page, "SJ2024CV01234")

        assert result.case_number == "SJ2024CV01234"
        assert result.court == "Tribunal de Primera Instancia San Juan"
        assert result.status == "Activo"
        assert len(result.parties) == 2

    def test_parse_empty_page(self):
        source = TribunalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        result = source._parse_result(mock_page, "JUAN PEREZ")

        assert result.search_term == "JUAN PEREZ"
        assert result.case_number == ""
        assert result.parties == []

    def test_parse_details_collected(self):
        source = TribunalesSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "Sala: Civil\nRegión: Bayamón\n"

        result = source._parse_result(mock_page, "test")

        assert "Sala" in result.details
        assert result.details["Sala"] == "Civil"
