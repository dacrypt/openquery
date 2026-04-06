"""Tests for uy.ursea — URSEA energy/water regulator source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestUrseaSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.ursea import UrseaSource
        meta = UrseaSource().meta()
        assert meta.name == "uy.ursea"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.uy.ursea import UrseaSource
        src = UrseaSource()
        with pytest.raises(SourceError, match="entity_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestUrseaModel:
    def test_model_defaults(self):
        from openquery.models.uy.ursea import UrseaResult
        r = UrseaResult(search_term="UTE")
        assert r.search_term == "UTE"
        assert r.entity_name == ""
        assert r.regulation_status == ""

    def test_model_roundtrip(self):
        from openquery.models.uy.ursea import UrseaResult
        r = UrseaResult(search_term="UTE", entity_name="UTE S.A.", regulation_status="Habilitada")
        data = r.model_dump_json()
        r2 = UrseaResult.model_validate_json(data)
        assert r2.regulation_status == "Habilitada"

    def test_audit_excluded(self):
        from openquery.models.uy.ursea import UrseaResult
        r = UrseaResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
