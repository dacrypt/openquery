"""Unit tests for Chile ISP health product registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.cl.isp import IspResult
from openquery.sources.cl.isp import IspSource


class TestIspResult:
    """Test IspResult model."""

    def test_default_values(self):
        data = IspResult()
        assert data.search_term == ""
        assert data.product_name == ""
        assert data.registration_number == ""
        assert data.status == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IspResult(
            search_term="ibuprofeno",
            product_name="Ibuprofeno 400mg",
            registration_number="ISP-CL-78901",
            status="Vigente",
        )
        json_str = data.model_dump_json()
        restored = IspResult.model_validate_json(json_str)
        assert restored.search_term == "ibuprofeno"
        assert restored.registration_number == "ISP-CL-78901"

    def test_audit_excluded_from_json(self):
        data = IspResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestIspSourceMeta:
    """Test IspSource metadata."""

    def test_meta_name(self):
        source = IspSource()
        assert source.meta().name == "cl.isp"

    def test_meta_country(self):
        source = IspSource()
        assert source.meta().country == "CL"

    def test_meta_requires_browser(self):
        source = IspSource()
        assert source.meta().requires_browser is True

    def test_meta_rate_limit(self):
        source = IspSource()
        assert source.meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        source = IspSource()
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = IspSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test IspSource._parse_result parsing logic."""

    def test_parse_found(self):
        source = IspSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Nombre: Ibuprofeno 400mg\n"
            "Registro Sanitario N°: ISP-CL-78901\n"
            "Estado: Vigente\n"
            "Inscrito autorizado\n"
        )
        result = source._parse_result(mock_page, "ibuprofeno")
        assert result.details["found"] is True

    def test_parse_not_found(self):
        source = IspSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "No se encontraron resultados."
        result = source._parse_result(mock_page, "inexistente")
        assert result.details["found"] is False
        assert result.status == "No encontrado"

    def test_query_requires_product_name(self):
        from openquery.exceptions import SourceError
        from openquery.sources.base import DocumentType, QueryInput

        source = IspSource()
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        try:
            source.query(inp)
            assert False, "Should have raised SourceError"
        except SourceError as e:
            assert "cl.isp" in str(e)
