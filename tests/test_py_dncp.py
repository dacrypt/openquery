"""Unit tests for py.dncp source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.models.py.dncp import PyDncpContract, PyDncpResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.py.dncp import PyDncpSource


class TestPyDncpResult:
    """Test PyDncpResult model."""

    def test_default_values(self):
        data = PyDncpResult()
        assert data.search_term == ""
        assert data.total_contracts == 0
        assert data.contracts == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = PyDncpResult(
            search_term="Proveedor SA",
            total_contracts=2,
            contracts=[
                PyDncpContract(
                    convocatoria="Licitación 001",
                    monto="100000",
                    estado="Adjudicado",
                    fecha="2023-01-01",
                )
            ],
        )
        json_str = data.model_dump_json()
        restored = PyDncpResult.model_validate_json(json_str)
        assert restored.search_term == "Proveedor SA"
        assert restored.total_contracts == 2
        assert len(restored.contracts) == 1
        assert restored.contracts[0].convocatoria == "Licitación 001"

    def test_audit_excluded_from_json(self):
        data = PyDncpResult(search_term="test", audit=b"pdf-bytes")
        json_str = data.model_dump_json()
        assert "audit" not in json_str


class TestPyDncpContract:
    """Test PyDncpContract model."""

    def test_default_values(self):
        c = PyDncpContract()
        assert c.convocatoria == ""
        assert c.monto == ""
        assert c.estado == ""
        assert c.fecha == ""


class TestPyDncpSourceMeta:
    """Test PyDncpSource metadata."""

    def test_meta_name(self):
        source = PyDncpSource()
        meta = source.meta()
        assert meta.name == "py.dncp"

    def test_meta_country(self):
        source = PyDncpSource()
        meta = source.meta()
        assert meta.country == "PY"

    def test_meta_rate_limit(self):
        source = PyDncpSource()
        meta = source.meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = PyDncpSource()
        meta = source.meta()
        assert meta.requires_browser is True

    def test_meta_supported_inputs(self):
        source = PyDncpSource()
        meta = source.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_default_timeout(self):
        source = PyDncpSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = PyDncpSource(timeout=45.0)
        assert source._timeout == 45.0

    def test_empty_supplier_name_raises(self):
        src = PyDncpSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_supplier_name_from_document_number(self):
        inp = QueryInput(document_type=DocumentType.CUSTOM, document_number="Proveedor SA")
        assert inp.document_number == "Proveedor SA"


class TestPyDncpParseResult:
    """Test result parsing logic."""

    def _parse(self, body_text: str, search_term: str = "Proveedor SA", rows=None):
        source = PyDncpSource()
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        if rows is None:
            mock_page.query_selector_all.return_value = []
        else:
            mock_page.query_selector_all.return_value = rows
        return source._parse_result(mock_page, search_term)

    def test_parse_empty_page(self):
        result = self._parse("")
        assert result.search_term == "Proveedor SA"
        assert result.total_contracts == 0
        assert result.contracts == []

    def test_parse_table_rows(self):
        mock_header = MagicMock()
        mock_header.query_selector_all.return_value = []
        mock_row = MagicMock()
        cell1 = MagicMock()
        cell1.inner_text.return_value = "Licitación 001"
        cell2 = MagicMock()
        cell2.inner_text.return_value = "100000"
        cell3 = MagicMock()
        cell3.inner_text.return_value = "Adjudicado"
        cell4 = MagicMock()
        cell4.inner_text.return_value = "2023-01-01"
        mock_row.query_selector_all.return_value = [cell1, cell2, cell3, cell4]
        result = self._parse("", rows=[mock_header, mock_row])
        assert len(result.contracts) == 1
        assert result.contracts[0].convocatoria == "Licitación 001"
        assert result.contracts[0].estado == "Adjudicado"
        assert result.total_contracts == 1

    def test_search_term_preserved(self):
        result = self._parse("", search_term="EMPRESA ABC")
        assert result.search_term == "EMPRESA ABC"

    def test_model_roundtrip(self):
        r = PyDncpResult(search_term="Proveedor SA", total_contracts=1)
        data = r.model_dump_json()
        r2 = PyDncpResult.model_validate_json(data)
        assert r2.search_term == "Proveedor SA"
        assert r2.total_contracts == 1
