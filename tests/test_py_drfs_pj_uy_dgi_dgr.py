"""Tests for new sources — PY (pj, drfs), UY (dgi, dgr).

Tests meta(), input validation, model roundtrips, and registry integration.
"""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# PARAGUAY — py.pj
# ===========================================================================

class TestPyPjResult:
    def test_default_values(self):
        from openquery.models.py.pj import PyPjResult
        r = PyPjResult(case_number="123-2024")
        assert r.case_number == "123-2024"
        assert r.status == ""
        assert r.court == ""
        assert r.parties == ""
        assert r.last_action == ""
        assert r.details == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.py.pj import PyPjResult
        r = PyPjResult(
            case_number="123-2024",
            status="EN TRAMITE",
            court="JUZGADO CIVIL 1",
            parties="GARCIA vs LOPEZ",
            last_action="PROVIDENCIA",
        )
        r2 = PyPjResult.model_validate_json(r.model_dump_json())
        assert r2.case_number == "123-2024"
        assert r2.status == "EN TRAMITE"
        assert r2.court == "JUZGADO CIVIL 1"
        assert r2.parties == "GARCIA vs LOPEZ"
        assert r2.last_action == "PROVIDENCIA"

    def test_audit_excluded_from_dump(self):
        from openquery.models.py.pj import PyPjResult
        r = PyPjResult(case_number="123-2024")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestPyPjSourceMeta:
    def test_meta(self):
        from openquery.sources.py.pj import PyPjSource
        meta = PyPjSource().meta()
        assert meta.name == "py.pj"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_case_number(self):
        from openquery.sources.py.pj import PyPjSource
        src = PyPjSource()
        with pytest.raises(SourceError, match="Case number is required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))

    def test_query_accepts_case_number_from_extra(self):
        from unittest.mock import MagicMock, patch

        from openquery.sources.py.pj import PyPjSource
        src = PyPjSource()
        mock_result = MagicMock()
        with patch.object(src, "_query", return_value=mock_result) as mock_q:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"case_number": "456-2024"},
            ))
            mock_q.assert_called_once_with("456-2024", audit=False)


# ===========================================================================
# PARAGUAY — py.drfs
# ===========================================================================

class TestPyDrfsResult:
    def test_default_values(self):
        from openquery.models.py.drfs import PyDrfsResult
        r = PyDrfsResult(search_term="EMPRESA SA")
        assert r.search_term == "EMPRESA SA"
        assert r.company_name == ""
        assert r.registration_status == ""
        assert r.folio == ""
        assert r.company_type == ""
        assert r.details == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.py.drfs import PyDrfsResult
        r = PyDrfsResult(
            search_term="EMPRESA SA",
            company_name="EMPRESA SOCIEDAD ANONIMA",
            registration_status="ACTIVA",
            folio="12345",
            company_type="S.A.",
        )
        r2 = PyDrfsResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "EMPRESA SA"
        assert r2.company_name == "EMPRESA SOCIEDAD ANONIMA"
        assert r2.registration_status == "ACTIVA"
        assert r2.folio == "12345"
        assert r2.company_type == "S.A."

    def test_audit_excluded_from_dump(self):
        from openquery.models.py.drfs import PyDrfsResult
        r = PyDrfsResult(search_term="EMPRESA SA")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestPyDrfsSourceMeta:
    def test_meta(self):
        from openquery.sources.py.drfs import PyDrfsSource
        meta = PyDrfsSource().meta()
        assert meta.name == "py.drfs"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_search_term(self):
        from openquery.sources.py.drfs import PyDrfsSource
        src = PyDrfsSource()
        with pytest.raises(SourceError, match="Company name or registration number is required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))

    def test_query_accepts_company_name_from_extra(self):
        from unittest.mock import MagicMock, patch

        from openquery.sources.py.drfs import PyDrfsSource
        src = PyDrfsSource()
        mock_result = MagicMock()
        with patch.object(src, "_query", return_value=mock_result) as mock_q:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"company_name": "EMPRESA SA"},
            ))
            mock_q.assert_called_once_with("EMPRESA SA", audit=False)


# ===========================================================================
# URUGUAY — uy.dgi
# ===========================================================================

class TestUyDgiResult:
    def test_default_values(self):
        from openquery.models.uy.dgi import UyDgiResult
        r = UyDgiResult(rut="210000000001")
        assert r.rut == "210000000001"
        assert r.contributor_status == ""
        assert r.rut_valid == ""
        assert r.tax_compliance == ""
        assert r.details == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.uy.dgi import UyDgiResult
        r = UyDgiResult(
            rut="210000000001",
            contributor_status="ACTIVO",
            rut_valid="SI",
            tax_compliance="AL DIA",
        )
        r2 = UyDgiResult.model_validate_json(r.model_dump_json())
        assert r2.rut == "210000000001"
        assert r2.contributor_status == "ACTIVO"
        assert r2.rut_valid == "SI"
        assert r2.tax_compliance == "AL DIA"

    def test_audit_excluded_from_dump(self):
        from openquery.models.uy.dgi import UyDgiResult
        r = UyDgiResult(rut="210000000001")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestUyDgiSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.dgi import UyDgiSource
        meta = UyDgiSource().meta()
        assert meta.name == "uy.dgi"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_rut(self):
        from openquery.sources.uy.dgi import UyDgiSource
        src = UyDgiSource()
        with pytest.raises(SourceError, match="RUT"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))

    def test_query_accepts_rut_from_extra(self):
        from unittest.mock import MagicMock, patch

        from openquery.sources.uy.dgi import UyDgiSource
        src = UyDgiSource()
        mock_result = MagicMock()
        with patch.object(src, "_query", return_value=mock_result) as mock_q:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"rut": "210000000001"},
            ))
            mock_q.assert_called_once_with("210000000001", audit=False)


# ===========================================================================
# URUGUAY — uy.dgr
# ===========================================================================

class TestUyDgrResult:
    def test_default_values(self):
        from openquery.models.uy.dgr import UyDgrResult
        r = UyDgrResult(search_term="EMPRESA SA")
        assert r.search_term == "EMPRESA SA"
        assert r.company_name == ""
        assert r.registration_status == ""
        assert r.company_type == ""
        assert r.details == ""
        assert r.audit is None

    def test_roundtrip(self):
        from openquery.models.uy.dgr import UyDgrResult
        r = UyDgrResult(
            search_term="EMPRESA SA",
            company_name="EMPRESA SOCIEDAD ANONIMA",
            registration_status="VIGENTE",
            company_type="SOCIEDAD ANONIMA",
        )
        r2 = UyDgrResult.model_validate_json(r.model_dump_json())
        assert r2.search_term == "EMPRESA SA"
        assert r2.company_name == "EMPRESA SOCIEDAD ANONIMA"
        assert r2.registration_status == "VIGENTE"
        assert r2.company_type == "SOCIEDAD ANONIMA"

    def test_audit_excluded_from_dump(self):
        from openquery.models.uy.dgr import UyDgrResult
        r = UyDgrResult(search_term="EMPRESA SA")
        r.audit = b"pdf_bytes"
        data = r.model_dump()
        assert "audit" not in data


class TestUyDgrSourceMeta:
    def test_meta(self):
        from openquery.sources.uy.dgr import UyDgrSource
        meta = UyDgrSource().meta()
        assert meta.name == "uy.dgr"
        assert meta.country == "UY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_query_requires_search_term(self):
        from openquery.sources.uy.dgr import UyDgrSource
        src = UyDgrSource()
        with pytest.raises(SourceError, match="Company name or registration number is required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="", extra={}))

    def test_query_accepts_company_name_from_extra(self):
        from unittest.mock import MagicMock, patch

        from openquery.sources.uy.dgr import UyDgrSource
        src = UyDgrSource()
        mock_result = MagicMock()
        with patch.object(src, "_query", return_value=mock_result) as mock_q:
            src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"company_name": "EMPRESA SA"},
            ))
            mock_q.assert_called_once_with("EMPRESA SA", audit=False)


# ===========================================================================
# Registry integration
# ===========================================================================

class TestNewSourcesRegistry:
    def test_all_four_registered(self):
        from openquery.sources import list_sources
        names = [s.meta().name for s in list_sources()]
        assert "py.pj" in names
        assert "py.drfs" in names
        assert "uy.dgi" in names
        assert "uy.dgr" in names
