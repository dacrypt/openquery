"""Tests for ve.seniat — Venezuela SENIAT RIF tax registry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestSeniatResult — model tests
# ===========================================================================


class TestSeniatResult:
    def test_defaults(self):
        from openquery.models.ve.seniat import SeniatResult

        r = SeniatResult()
        assert r.rif == ""
        assert r.taxpayer_name == ""
        assert r.tax_status == ""
        assert r.taxpayer_type == ""
        assert r.details == {}
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ve.seniat import SeniatResult

        r = SeniatResult(
            rif="J-12345678-9",
            taxpayer_name="EMPRESA EJEMPLO C.A.",
            tax_status="ACTIVO",
            taxpayer_type="JURIDICO",
        )
        dumped = r.model_dump_json()
        restored = SeniatResult.model_validate_json(dumped)
        assert restored.rif == "J-12345678-9"
        assert restored.taxpayer_name == "EMPRESA EJEMPLO C.A."
        assert restored.tax_status == "ACTIVO"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.seniat import SeniatResult

        r = SeniatResult(audit=b"pdf-bytes")
        data = r.model_dump()
        assert "audit" not in data

    def test_details_dict(self):
        from openquery.models.ve.seniat import SeniatResult

        r = SeniatResult(details={"Nombre": "EMPRESA EJEMPLO C.A.", "Estado": "ACTIVO"})
        assert r.details["Nombre"] == "EMPRESA EJEMPLO C.A."


# ===========================================================================
# TestSeniatSourceMeta
# ===========================================================================


class TestSeniatSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ve.seniat import SeniatSource

        assert SeniatSource().meta().name == "ve.seniat"

    def test_meta_country(self):
        from openquery.sources.ve.seniat import SeniatSource

        assert SeniatSource().meta().country == "VE"

    def test_meta_requires_browser(self):
        from openquery.sources.ve.seniat import SeniatSource

        assert SeniatSource().meta().requires_browser is True

    def test_meta_requires_captcha(self):
        from openquery.sources.ve.seniat import SeniatSource

        assert SeniatSource().meta().requires_captcha is True

    def test_meta_supported_inputs(self):
        from openquery.sources.ve.seniat import SeniatSource

        assert DocumentType.CUSTOM in SeniatSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.ve.seniat import SeniatSource

        assert SeniatSource().meta().rate_limit_rpm == 5


# ===========================================================================
# TestSeniatQuery — input validation
# ===========================================================================


class TestSeniatQuery:
    def test_empty_rif_raises(self):
        from openquery.sources.ve.seniat import SeniatSource

        src = SeniatSource()
        with pytest.raises(SourceError, match="RIF"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_rif_from_document_number(self):
        from openquery.models.ve.seniat import SeniatResult
        from openquery.sources.ve.seniat import SeniatSource

        src = SeniatSource()
        src._query = MagicMock(return_value=SeniatResult(rif="J-12345678-9"))
        result = src.query(
            QueryInput(document_type=DocumentType.CUSTOM, document_number="J-12345678-9")
        )
        src._query.assert_called_once_with(rif="J-12345678-9", audit=False)
        assert result.rif == "J-12345678-9"

    def test_rif_from_extra(self):
        from openquery.models.ve.seniat import SeniatResult
        from openquery.sources.ve.seniat import SeniatSource

        src = SeniatSource()
        src._query = MagicMock(return_value=SeniatResult(rif="V-87654321-0"))
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="",
                extra={"rif": "V-87654321-0"},
            )
        )
        src._query.assert_called_once_with(rif="V-87654321-0", audit=False)
        assert result.rif == "V-87654321-0"


# ===========================================================================
# TestSeniatParseResult — parsing logic
# ===========================================================================


class TestSeniatParseResult:
    def _make_page(self, body_text: str) -> MagicMock:
        page = MagicMock()
        page.inner_text.return_value = body_text
        return page

    def _parse(self, body_text: str, rif: str = "J-12345678-9") -> object:
        from openquery.sources.ve.seniat import SeniatSource

        return SeniatSource()._parse_result(self._make_page(body_text), rif)

    def test_taxpayer_name_extracted(self):
        body = "Nombre: EMPRESA EJEMPLO C.A.\nEstado: ACTIVO\n"
        result = self._parse(body)
        assert result.taxpayer_name == "EMPRESA EJEMPLO C.A."

    def test_tax_status_extracted(self):
        body = "Nombre: EMPRESA EJEMPLO C.A.\nEstado: ACTIVO\n"
        result = self._parse(body)
        assert result.tax_status == "ACTIVO"

    def test_taxpayer_type_extracted(self):
        body = "Tipo: JURIDICO\n"
        result = self._parse(body)
        assert result.taxpayer_type == "JURIDICO"

    def test_rif_preserved(self):
        result = self._parse("", rif="J-12345678-9")
        assert result.rif == "J-12345678-9"

    def test_empty_body_returns_defaults(self):
        result = self._parse("")
        assert result.taxpayer_name == ""
        assert result.tax_status == ""
        assert result.taxpayer_type == ""

    def test_details_populated(self):
        body = "Nombre: EMPRESA EJEMPLO C.A.\nEstado: ACTIVO\n"
        result = self._parse(body)
        assert isinstance(result.details, dict)
        assert len(result.details) > 0

    def test_queried_at_set(self):
        result = self._parse("")
        assert isinstance(result.queried_at, datetime)

    def test_regex_fallback_nombre(self):
        body = "Razón Social: OTRA EMPRESA S.A.\n"
        result = self._parse(body)
        assert result.taxpayer_name == "OTRA EMPRESA S.A."

    def test_regex_fallback_condicion(self):
        body = "Condición: INACTIVO\n"
        result = self._parse(body)
        assert result.tax_status == "INACTIVO"


# ===========================================================================
# Integration test (skipped by default)
# ===========================================================================


@pytest.mark.integration
class TestSeniatIntegration:
    def test_query_by_rif(self):
        from openquery.sources.ve.seniat import SeniatSource

        src = SeniatSource(headless=True)
        result = src.query(
            QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number="J-00000013-7",
            )
        )
        assert isinstance(result.rif, str)
        assert isinstance(result.taxpayer_name, str)
