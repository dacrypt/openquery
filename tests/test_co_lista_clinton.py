"""Unit tests for Colombia Lista Clinton (OFAC SDN) source."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openquery.models.co.lista_clinton import ListaClintonResult
from openquery.sources.co.lista_clinton import ListaClintonSource


class TestListaClintonResult:
    """Test ListaClintonResult model."""

    def test_default_values(self):
        data = ListaClintonResult()
        assert data.search_term == ""
        assert data.is_listed is False
        assert data.list_type == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = ListaClintonResult(
            search_term="Pablo Escobar",
            is_listed=True,
            list_type="SDN",
        )
        json_str = data.model_dump_json()
        restored = ListaClintonResult.model_validate_json(json_str)
        assert restored.search_term == "Pablo Escobar"
        assert restored.is_listed is True
        assert restored.list_type == "SDN"

    def test_audit_excluded_from_json(self):
        data = ListaClintonResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_not_listed_default(self):
        data = ListaClintonResult(search_term="John Smith")
        assert data.is_listed is False
        assert data.list_type == ""


class TestListaClintonSourceMeta:
    """Test ListaClintonSource metadata."""

    def test_meta_name(self):
        source = ListaClintonSource()
        assert source.meta().name == "co.lista_clinton"

    def test_meta_country(self):
        source = ListaClintonSource()
        assert source.meta().country == "CO"

    def test_meta_requires_browser(self):
        source = ListaClintonSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = ListaClintonSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = ListaClintonSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = ListaClintonSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = ListaClintonSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test ListaClintonSource query logic."""

    def test_query_not_listed(self):
        source = ListaClintonSource()
        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = "no results found for your search"
            mock_get.return_value = mock_resp
            result = source._query("John Smith")
        assert result.is_listed is False
        assert result.list_type == ""

    def test_query_listed(self):
        source = ListaClintonSource()
        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = "SDN list match found Specially Designated"
            mock_get.return_value = mock_resp
            result = source._query("known bad actor")
        assert result.is_listed is True
        assert result.list_type == "SDN"

    def test_query_requires_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = ListaClintonSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "co.lista_clinton" in str(e)
