"""Tests for pa.panamacompra — Panama government contracts (OCDS API)."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


# ===========================================================================
# TestResult
# ===========================================================================

class TestResult:
    def test_default_values(self):
        from openquery.models.pa.panamacompra import PanamaCompraResult
        r = PanamaCompraResult()
        assert r.search_term == ""
        assert r.total == 0
        assert r.contracts == []
        assert r.audit is None

    def test_contract_defaults(self):
        from openquery.models.pa.panamacompra import PanamaCompraContract
        c = PanamaCompraContract()
        assert c.ocid == ""
        assert c.title == ""
        assert c.value == ""
        assert c.currency == ""
        assert c.buyer == ""
        assert c.supplier == ""

    def test_audit_excluded_from_json(self):
        from openquery.models.pa.panamacompra import PanamaCompraResult
        r = PanamaCompraResult(search_term="test", total=0)
        r.audit = {"evidence": "data"}
        data = r.model_dump_json()
        assert "audit" not in data

    def test_model_roundtrip(self):
        from openquery.models.pa.panamacompra import PanamaCompraContract, PanamaCompraResult
        r = PanamaCompraResult(
            search_term="MINSA",
            total=1,
            contracts=[PanamaCompraContract(ocid="ocds-abc-001", title="Compra de medicamentos", value="50000", currency="USD")],
        )
        r2 = PanamaCompraResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "MINSA"
        assert r2.total == 1
        assert r2.contracts[0].ocid == "ocds-abc-001"
        assert r2.contracts[0].currency == "USD"


# ===========================================================================
# TestSourceMeta
# ===========================================================================

class TestSourceMeta:
    def test_meta_name(self):
        from openquery.sources.pa.panamacompra import PanamaCompraSource
        meta = PanamaCompraSource().meta()
        assert meta.name == "pa.panamacompra"

    def test_meta_country(self):
        from openquery.sources.pa.panamacompra import PanamaCompraSource
        meta = PanamaCompraSource().meta()
        assert meta.country == "PA"

    def test_meta_no_browser(self):
        from openquery.sources.pa.panamacompra import PanamaCompraSource
        meta = PanamaCompraSource().meta()
        assert meta.requires_browser is False
        assert meta.requires_captcha is False

    def test_meta_supports_custom(self):
        from openquery.sources.pa.panamacompra import PanamaCompraSource
        meta = PanamaCompraSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pa.panamacompra import PanamaCompraSource
        meta = PanamaCompraSource().meta()
        assert meta.rate_limit_rpm == 10


# ===========================================================================
# TestParseResult
# ===========================================================================

class TestParseResult:
    def _make_source(self):
        from openquery.sources.pa.panamacompra import PanamaCompraSource
        return PanamaCompraSource()

    def test_parse_releases(self):
        src = self._make_source()
        data = {
            "count": 1,
            "releases": [
                {
                    "ocid": "ocds-pa-001",
                    "date": "2024-01-15",
                    "buyer": {"name": "Ministerio de Salud"},
                    "tender": {
                        "title": "Adquisición de equipos médicos",
                        "description": "Equipos para hospitales",
                        "status": "active",
                        "value": {"amount": 100000, "currency": "PAB"},
                    },
                    "awards": [{"suppliers": [{"name": "MedEquip SA"}]}],
                }
            ],
        }
        result = src._parse_response(data, "MINSA")
        assert result.search_term == "MINSA"
        assert result.total == 1
        assert len(result.contracts) == 1
        c = result.contracts[0]
        assert c.ocid == "ocds-pa-001"
        assert c.title == "Adquisición de equipos médicos"
        assert c.buyer == "Ministerio de Salud"
        assert c.supplier == "MedEquip SA"
        assert c.value == "100000"
        assert c.currency == "PAB"
        assert c.date == "2024-01-15"

    def test_parse_empty_releases(self):
        src = self._make_source()
        data = {"count": 0, "releases": []}
        result = src._parse_response(data, "XYZ")
        assert result.total == 0
        assert result.contracts == []

    def test_parse_missing_optional_fields(self):
        src = self._make_source()
        data = {
            "releases": [
                {"ocid": "ocds-pa-002", "date": "2024-03-01"},
            ]
        }
        result = src._parse_response(data, "test")
        assert len(result.contracts) == 1
        c = result.contracts[0]
        assert c.ocid == "ocds-pa-002"
        assert c.buyer == ""
        assert c.supplier == ""
        assert c.value == ""

    def test_query_missing_search_raises(self):
        src = self._make_source()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_query_uses_document_number(self):
        """document_number is used as fallback search term."""
        from unittest.mock import patch
        src = self._make_source()
        mock_result = src._parse_response({"count": 0, "releases": []}, "TEST-CORP")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="TEST-CORP"))
            m.assert_called_once_with("TEST-CORP")

    def test_query_uses_extra_q(self):
        from unittest.mock import patch
        src = self._make_source()
        mock_result = src._parse_response({"count": 0, "releases": []}, "MINSA")
        with patch.object(src, "_query", return_value=mock_result) as m:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"q": "MINSA"},
            ))
            m.assert_called_once_with("MINSA")
