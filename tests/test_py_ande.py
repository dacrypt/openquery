"""Tests for py.ande — Paraguay ANDE electricity utility source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestAndeParseResult:
    def _parse(self, body_text: str, account_number: str = "123456789"):
        from openquery.sources.py.ande import AndeSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = AndeSource()
        return src._parse_result(page, account_number)

    def test_empty_body_returns_empty_result(self):
        result = self._parse("")
        assert result.account_holder == ""
        assert result.account_status == ""

    def test_account_number_preserved(self):
        result = self._parse("", account_number="987654321")
        assert result.account_number == "987654321"

    def test_parses_account_holder(self):
        body = "Titular: Juan Paraguay\nEstado: Al día"
        result = self._parse(body)
        assert result.account_holder == "Juan Paraguay"

    def test_parses_balance(self):
        body = "Saldo: Gs. 150,000\nEstado: Deudor"
        result = self._parse(body)
        assert result.balance == "Gs. 150,000"

    def test_model_roundtrip(self):
        from openquery.models.py.ande import AndeResult

        r = AndeResult(account_number="123456789", account_holder="Juan PY", account_status="Al día")  # noqa: E501
        data = r.model_dump_json()
        r2 = AndeResult.model_validate_json(data)
        assert r2.account_number == "123456789"

    def test_audit_excluded_from_json(self):
        from openquery.models.py.ande import AndeResult

        r = AndeResult(account_number="123456789", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestAndeSourceMeta:
    def test_meta(self):
        from openquery.sources.py.ande import AndeSource

        meta = AndeSource().meta()
        assert meta.name == "py.ande"
        assert meta.country == "PY"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_account_raises(self):
        from openquery.sources.py.ande import AndeSource

        src = AndeSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))
