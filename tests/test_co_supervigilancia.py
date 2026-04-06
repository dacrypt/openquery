"""Tests for co.supervigilancia — private security companies source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSupervigilanciaSourceMeta:
    def test_meta(self):
        from openquery.sources.co.supervigilancia import SupervigilanciaSource
        meta = SupervigilanciaSource().meta()
        assert meta.name == "co.supervigilancia"
        assert meta.country == "CO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_input_raises(self):
        from openquery.sources.co.supervigilancia import SupervigilanciaSource
        src = SupervigilanciaSource()
        with pytest.raises(SourceError, match="company_name"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestSupervigilanciaModel:
    def test_model_defaults(self):
        from openquery.models.co.supervigilancia import SupervigilanciaResult
        r = SupervigilanciaResult(search_term="Seguridad Total")
        assert r.search_term == "Seguridad Total"
        assert r.company_name == ""
        assert r.license_status == ""

    def test_model_roundtrip(self):
        from openquery.models.co.supervigilancia import SupervigilanciaResult
        r = SupervigilanciaResult(search_term="test", company_name="Empresa ABC", license_status="Vigente")  # noqa: E501
        data = r.model_dump_json()
        r2 = SupervigilanciaResult.model_validate_json(data)
        assert r2.license_status == "Vigente"

    def test_audit_excluded(self):
        from openquery.models.co.supervigilancia import SupervigilanciaResult
        r = SupervigilanciaResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
