"""Unit tests for Uruguay BCU central bank supervised entities source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.uy.bcu import BcuResult
from openquery.sources.uy.bcu import BcuSource


class TestBcuResult:
    """Test BcuResult model."""

    def test_default_values(self):
        data = BcuResult()
        assert data.search_term == ""
        assert data.entity_name == ""
        assert data.entity_type == ""
        assert data.supervision_status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = BcuResult(
            search_term="BANCO REPUBLIC",
            entity_name="BANCO DE LA REPUBLICA ORIENTAL DEL URUGUAY",
            entity_type="BANCO PUBLICO",
            supervision_status="ACTIVO",
        )
        json_str = data.model_dump_json()
        restored = BcuResult.model_validate_json(json_str)
        assert restored.search_term == "BANCO REPUBLIC"
        assert restored.entity_name == "BANCO DE LA REPUBLICA ORIENTAL DEL URUGUAY"
        assert restored.entity_type == "BANCO PUBLICO"
        assert restored.supervision_status == "ACTIVO"

    def test_audit_excluded_from_json(self):
        data = BcuResult(search_term="BANCO TEST", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestBcuSourceMeta:
    """Test BcuSource metadata."""

    def test_meta_name(self):
        source = BcuSource()
        assert source.meta().name == "uy.bcu"

    def test_meta_country(self):
        source = BcuSource()
        assert source.meta().country == "UY"

    def test_meta_requires_browser(self):
        source = BcuSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = BcuSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = BcuSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = BcuSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = BcuSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = BcuSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test BcuSource._parse_result parsing logic."""

    def test_parse_from_table(self):
        source = BcuSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""

        mock_row0 = MagicMock()
        mock_row1 = MagicMock()
        cell0 = MagicMock()
        cell0.inner_text.return_value = "BANCO REPUBLIC"
        cell1 = MagicMock()
        cell1.inner_text.return_value = "BANCO PRIVADO"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "AUTORIZADO"
        mock_row1.query_selector_all.return_value = [cell0, cell1, cell2]
        mock_page.query_selector_all.return_value = [mock_row0, mock_row1]

        result = source._parse_result(mock_page, "BANCO REPUBLIC")
        assert result.search_term == "BANCO REPUBLIC"
        assert result.entity_name == "BANCO REPUBLIC"
        assert result.entity_type == "BANCO PRIVADO"
        assert result.supervision_status == "AUTORIZADO"

    def test_parse_empty_page(self):
        source = BcuSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = ""
        mock_page.query_selector_all.return_value = []

        result = source._parse_result(mock_page, "ENTIDAD INEXISTENTE")
        assert result.search_term == "ENTIDAD INEXISTENTE"
        assert result.entity_name == ""
