"""Tests for ec.senae — SENAE customs declarations source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSenaeSourceMeta:
    def test_meta(self):
        from openquery.sources.ec.senae import SenaeSource
        meta = SenaeSource().meta()
        assert meta.name == "ec.senae"
        assert meta.country == "EC"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_declaration_raises(self):
        from openquery.sources.ec.senae import SenaeSource
        src = SenaeSource()
        with pytest.raises(SourceError, match="[Dd]eclaration"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSenaeModel:
    def test_model_defaults(self):
        from openquery.models.ec.senae import SenaeResult
        r = SenaeResult(declaration_number="040-2024-10-00001234")
        assert r.declaration_number == "040-2024-10-00001234"
        assert r.status == ""
        assert r.importer == ""

    def test_model_roundtrip(self):
        from openquery.models.ec.senae import SenaeResult
        r = SenaeResult(declaration_number="040-2024-10-00001234", status="Levante autorizado", importer="Empresa EC")  # noqa: E501
        data = r.model_dump_json()
        r2 = SenaeResult.model_validate_json(data)
        assert r2.status == "Levante autorizado"

    def test_audit_excluded(self):
        from openquery.models.ec.senae import SenaeResult
        r = SenaeResult(declaration_number="040-2024-10-00001234", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
