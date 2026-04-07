"""Tests for us.carquery — CarQuery vehicle trim specifications.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestUsCarQueryResult — model tests
# ===========================================================================


class TestUsCarQueryResult:
    def test_defaults(self):
        from openquery.models.us.carquery import UsCarQueryResult

        r = UsCarQueryResult()
        assert r.make == ""
        assert r.model == ""
        assert r.year == ""
        assert r.trim == ""
        assert r.body_style == ""
        assert r.engine == ""
        assert r.fuel_type == ""
        assert r.doors == ""
        assert r.seats == ""
        assert r.details == ""
        assert r.trims == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.us.carquery import UsCarQueryResult

        r = UsCarQueryResult(
            make="Toyota",
            model="Corolla",
            year="2020",
            fuel_type="Gasoline",
        )
        dumped = r.model_dump_json()
        restored = UsCarQueryResult.model_validate_json(dumped)
        assert restored.make == "Toyota"
        assert restored.year == "2020"

    def test_audit_excluded_from_json(self):
        from openquery.models.us.carquery import UsCarQueryResult

        r = UsCarQueryResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestUsCarQuerySourceMeta
# ===========================================================================


class TestUsCarQuerySourceMeta:
    def test_meta_name(self):
        from openquery.sources.us.carquery import CarQuerySource

        meta = CarQuerySource().meta()
        assert meta.name == "us.carquery"

    def test_meta_country(self):
        from openquery.sources.us.carquery import CarQuerySource

        meta = CarQuerySource().meta()
        assert meta.country == "US"

    def test_meta_no_captcha(self):
        from openquery.sources.us.carquery import CarQuerySource

        meta = CarQuerySource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.us.carquery import CarQuerySource

        meta = CarQuerySource().meta()
        assert meta.rate_limit_rpm == 20

    def test_meta_supports_custom(self):
        from openquery.sources.us.carquery import CarQuerySource

        meta = CarQuerySource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestUsCarQueryParseResult
# ===========================================================================

MOCK_CARQUERY_RESPONSE = {
    "Trims": [
        {
            "make_display": "Toyota",
            "model_name": "Corolla",
            "model_year": "2020",
            "model_trim": "LE",
            "model_body": "Sedan",
            "model_engine_cc": "1798",
            "model_engine_fuel": "Gasoline",
            "model_doors": "4",
            "model_seats": "5",
        }
    ]
}

# CarQuery wraps response in JSONP callback
MOCK_JSONP_TEXT = f"callback({json.dumps(MOCK_CARQUERY_RESPONSE)});"


class TestUsCarQueryParseResult:
    def _make_input(self, make: str = "Toyota", model: str = "Corolla", year: str = "2020") -> QueryInput:  # noqa: E501
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"make": make, "model": model, "year": year},
        )

    def test_missing_make_raises(self):
        from openquery.sources.us.carquery import CarQuerySource

        source = CarQuerySource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"model": "Corolla"},
        )
        with pytest.raises(SourceError, match="make"):
            source.query(inp)

    def test_successful_query(self):
        from openquery.sources.us.carquery import CarQuerySource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_JSONP_TEXT
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CarQuerySource()
            result = source.query(self._make_input())

        assert result.make == "Toyota"
        assert result.model == "Corolla"
        assert result.year == "2020"
        assert result.trim == "LE"
        assert result.body_style == "Sedan"
        assert result.fuel_type == "Gasoline"
        assert len(result.trims) == 1

    def test_strip_jsonp_plain_json(self):
        from openquery.sources.us.carquery import _strip_jsonp

        plain = '{"key": "value"}'
        assert _strip_jsonp(plain) == plain

    def test_strip_jsonp_callback(self):
        from openquery.sources.us.carquery import _strip_jsonp

        jsonp = 'callback({"key": "value"});'
        assert _strip_jsonp(jsonp) == '{"key": "value"}'

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.carquery import CarQuerySource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = CarQuerySource()
            with pytest.raises(SourceError, match="us.carquery"):
                source.query(self._make_input())
