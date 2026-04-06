"""Tests for co.agencia_tierras — ANT land restitution source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAgenciaTierrasSourceMeta:
    def test_meta(self):
        from openquery.sources.co.agencia_tierras import AgenciaTierrasSource
        meta = AgenciaTierrasSource().meta()
        assert meta.name == "co.agencia_tierras"
        assert meta.country == "CO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.co.agencia_tierras import AgenciaTierrasSource
        src = AgenciaTierrasSource()
        with pytest.raises(SourceError, match="case_number"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestAgenciaTierrasModel:
    def test_model_defaults(self):
        from openquery.models.co.agencia_tierras import AgenciaTierrasResult
        r = AgenciaTierrasResult(search_term="CASO-001")
        assert r.search_term == "CASO-001"
        assert r.case_status == ""

    def test_model_roundtrip(self):
        from openquery.models.co.agencia_tierras import AgenciaTierrasResult
        r = AgenciaTierrasResult(search_term="CASO-001", case_status="Activo")
        data = r.model_dump_json()
        r2 = AgenciaTierrasResult.model_validate_json(data)
        assert r2.case_status == "Activo"

    def test_audit_excluded(self):
        from openquery.models.co.agencia_tierras import AgenciaTierrasResult
        r = AgenciaTierrasResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
