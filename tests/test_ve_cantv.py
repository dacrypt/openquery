"""Tests for ve.cantv — Venezuela CANTV phone/internet service source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestCantvParseResult:
    def _parse(self, body_text: str, phone_number: str = "02125551234"):
        from openquery.sources.ve.cantv import CantvSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = CantvSource()
        return src._parse_result(page, phone_number)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.service_status == ""
        assert result.plan == ""
        assert result.debt_amount == ""

    def test_phone_number_preserved(self):
        result = self._parse("", phone_number="02125559999")
        assert result.phone_number == "02125559999"

    def test_parses_service_status(self):
        body = "Estado: Activo\nPlan: Internet 10MB\nDeuda: 500 Bs"
        result = self._parse(body)
        assert result.service_status == "Activo"

    def test_parses_plan(self):
        body = "Plan: Internet Plus 20MB\nEstado: Activo"
        result = self._parse(body)
        assert result.plan == "Internet Plus 20MB"

    def test_parses_debt_amount(self):
        body = "Deuda: 1200 Bs\nEstado: Suspendido"
        result = self._parse(body)
        assert result.debt_amount == "1200 Bs"

    def test_model_roundtrip(self):
        from openquery.models.ve.cantv import CantvResult

        r = CantvResult(
            phone_number="02125551234",
            service_status="Activo",
            plan="Fibra 50MB",
            debt_amount="0",
        )
        data = r.model_dump_json()
        r2 = CantvResult.model_validate_json(data)
        assert r2.phone_number == "02125551234"
        assert r2.service_status == "Activo"

    def test_audit_excluded_from_json(self):
        from openquery.models.ve.cantv import CantvResult

        r = CantvResult(phone_number="02125551234", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestCantvSourceMeta:
    def test_meta(self):
        from openquery.sources.ve.cantv import CantvSource

        meta = CantvSource().meta()
        assert meta.name == "ve.cantv"
        assert meta.country == "VE"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_phone_raises(self):
        from openquery.sources.ve.cantv import CantvSource

        src = CantvSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_document_number_used_as_phone(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="02125551234",
        )
        assert input_.document_number == "02125551234"

    def test_extra_phone_number(self):
        input_ = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"phone_number": "02125551234"},
        )
        assert input_.extra["phone_number"] == "02125551234"
