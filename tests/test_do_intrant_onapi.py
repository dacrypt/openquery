"""Tests for do.intrant and do.onapi sources.

Tests meta(), input validation, model roundtrips, and registry integration.
"""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# do.intrant — INTRANT driver license status
# ===========================================================================


class TestDoIntrantResult:
    def test_default_values(self):
        from openquery.models.do.intrant import DoIntrantResult

        r = DoIntrantResult(search_value="00100000001")
        assert r.search_value == "00100000001"
        assert r.license_status == ""
        assert r.expiration == ""
        assert r.fines_count == 0
        assert r.total_fines == ""
        assert r.details == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.do.intrant import DoIntrantResult

        r = DoIntrantResult(
            search_value="00100000001",
            license_status="ACTIVO",
            expiration="2025-12-31",
            fines_count=2,
            total_fines="RD$5,000.00",
        )
        r2 = DoIntrantResult.model_validate_json(r.model_dump_json())
        assert r2.search_value == "00100000001"
        assert r2.license_status == "ACTIVO"
        assert r2.expiration == "2025-12-31"
        assert r2.fines_count == 2
        assert r2.total_fines == "RD$5,000.00"

    def test_audit_excluded_from_dump(self):
        from openquery.models.do.intrant import DoIntrantResult

        r = DoIntrantResult(search_value="00100000001")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestDoIntrantSourceMeta:
    def test_meta(self):
        from openquery.sources.do.intrant import DoIntrantSource

        meta = DoIntrantSource().meta()
        assert meta.name == "do.intrant"
        assert meta.country == "DO"
        assert DocumentType.CEDULA in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_value(self):
        from openquery.sources.do.intrant import DoIntrantSource

        src = DoIntrantSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CEDULA, document_number="", extra={}))

    def test_registered(self):
        from openquery.sources import get_source

        src = get_source("do.intrant")
        assert src is not None
        assert src.meta().name == "do.intrant"


# ===========================================================================
# do.onapi — ONAPI trademark search
# ===========================================================================


class TestDoOnapiResult:
    def test_default_values(self):
        from openquery.models.do.onapi import DoOnapiResult

        r = DoOnapiResult(search_term="COCA COLA")
        assert r.search_term == "COCA COLA"
        assert r.trademark_name == ""
        assert r.owner == ""
        assert r.status == ""
        assert r.registration_date == ""
        assert r.classes == ""
        assert r.details == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.do.onapi import DoOnapiResult

        r = DoOnapiResult(
            search_term="COCA COLA",
            trademark_name="COCA COLA",
            owner="THE COCA-COLA COMPANY",
            status="REGISTRADA",
            registration_date="2000-01-15",
            classes="32",
        )
        r2 = DoOnapiResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "COCA COLA"
        assert r2.trademark_name == "COCA COLA"
        assert r2.owner == "THE COCA-COLA COMPANY"
        assert r2.status == "REGISTRADA"
        assert r2.registration_date == "2000-01-15"
        assert r2.classes == "32"

    def test_audit_excluded_from_dump(self):
        from openquery.models.do.onapi import DoOnapiResult

        r = DoOnapiResult(search_term="TEST")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestDoOnapiSourceMeta:
    def test_meta(self):
        from openquery.sources.do.onapi import DoOnapiSource

        meta = DoOnapiSource().meta()
        assert meta.name == "do.onapi"
        assert meta.country == "DO"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_term(self):
        from openquery.sources.do.onapi import DoOnapiSource

        src = DoOnapiSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))

    def test_registered(self):
        from openquery.sources import get_source

        src = get_source("do.onapi")
        assert src is not None
        assert src.meta().name == "do.onapi"
