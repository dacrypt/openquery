"""Tests for intl.bis — BIS financial statistics.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestBisResult — model tests
# ===========================================================================


class TestBisResult:
    def test_defaults(self):
        from openquery.models.intl.bis import BisResult

        r = BisResult()
        assert r.dataset == ""
        assert r.dimensions == ""
        assert r.data_points == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.bis import BisDataPoint, BisResult

        r = BisResult(
            dataset="WS_CPMI_CT2",
            dimensions="5A.5J.USD.A",
            data_points=[
                BisDataPoint(period="2022", value="1234.5"),
                BisDataPoint(period="2021", value="1100.0"),
            ],
        )
        dumped = r.model_dump_json()
        restored = BisResult.model_validate_json(dumped)
        assert restored.dataset == "WS_CPMI_CT2"
        assert restored.dimensions == "5A.5J.USD.A"
        assert len(restored.data_points) == 2

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.bis import BisResult

        r = BisResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_data_point_defaults(self):
        from openquery.models.intl.bis import BisDataPoint

        dp = BisDataPoint()
        assert dp.period == ""
        assert dp.value == ""


# ===========================================================================
# TestBisSourceMeta
# ===========================================================================


class TestBisSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.bis import BisSource

        meta = BisSource().meta()
        assert meta.name == "intl.bis"

    def test_meta_country(self):
        from openquery.sources.intl.bis import BisSource

        meta = BisSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.bis import BisSource

        meta = BisSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.bis import BisSource

        meta = BisSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.bis import BisSource

        meta = BisSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestBisParseResult
# ===========================================================================

MOCK_BIS_RESPONSE = {
    "structure": {
        "name": "Payment and settlement statistics",
        "dimensions": {
            "observation": [
                {
                    "id": "TIME_PERIOD",
                    "values": [
                        {"id": "2021"},
                        {"id": "2022"},
                    ],
                }
            ]
        },
    },
    "dataSets": [
        {
            "series": {
                "0:0:0:0": {
                    "observations": {
                        "0": [1100.0, None],
                        "1": [1234.5, None],
                    }
                }
            }
        }
    ],
}


class TestBisParseResult:
    def _make_input(
        self, dataset: str = "WS_CPMI_CT2", dimensions: str = "5A.5J.USD.A"
    ) -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"dataset": dataset, "dimensions": dimensions},
        )

    def test_successful_query(self):
        from openquery.sources.intl.bis import BisSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_BIS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = BisSource()
            result = source.query(self._make_input())

        assert result.dataset == "WS_CPMI_CT2"
        assert result.dimensions == "5A.5J.USD.A"
        assert len(result.data_points) == 2
        assert result.data_points[0].period == "2021"
        assert result.data_points[0].value == "1100.0"
        assert result.details == "Payment and settlement statistics"

    def test_missing_dataset_raises(self):
        from openquery.sources.intl.bis import BisSource

        source = BisSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"dimensions": "5A.5J.USD.A"},
        )
        with pytest.raises(SourceError, match="dataset"):
            source.query(inp)

    def test_missing_dimensions_raises(self):
        from openquery.sources.intl.bis import BisSource

        source = BisSource()
        inp = QueryInput(
            document_number="WS_CPMI_CT2",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="dimensions"):
            source.query(inp)

    def test_empty_datasets(self):
        from openquery.sources.intl.bis import BisSource

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"structure": {}, "dataSets": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = BisSource()
            result = source.query(self._make_input())

        assert result.data_points == []

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.bis import BisSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = BisSource()
            with pytest.raises(SourceError, match="intl.bis"):
                source.query(self._make_input())
