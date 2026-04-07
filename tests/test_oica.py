"""Tests for intl.oica — OICA global vehicle production/sales."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestOicaResult — model tests
# ===========================================================================


class TestOicaResult:
    def test_defaults(self):
        from openquery.models.intl.oica import OicaResult

        r = OicaResult()
        assert r.search_term == ""
        assert r.total_countries == 0
        assert r.data == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.oica import OicaCountryData, OicaResult

        r = OicaResult(
            search_term="GERMANY | 2023",
            total_countries=1,
            data=[
                OicaCountryData(
                    country="Germany",
                    year="2023",
                    passenger_cars=3200000,
                    commercial_vehicles=400000,
                    total=3600000,
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = OicaResult.model_validate_json(dumped)
        assert restored.search_term == "GERMANY | 2023"
        assert len(restored.data) == 1
        assert restored.data[0].total == 3600000

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.oica import OicaResult

        r = OicaResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_country_data_defaults(self):
        from openquery.models.intl.oica import OicaCountryData

        d = OicaCountryData()
        assert d.country == ""
        assert d.year == ""
        assert d.passenger_cars == 0
        assert d.commercial_vehicles == 0
        assert d.total == 0


# ===========================================================================
# TestOicaSourceMeta
# ===========================================================================


class TestOicaSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.oica import OicaSource

        meta = OicaSource().meta()
        assert meta.name == "intl.oica"

    def test_meta_country(self):
        from openquery.sources.intl.oica import OicaSource

        meta = OicaSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.oica import OicaSource

        meta = OicaSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.oica import OicaSource

        meta = OicaSource().meta()
        assert meta.rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.intl.oica import OicaSource

        meta = OicaSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestOicaParseResult
# ===========================================================================

MOCK_OICA_CSV = """country,year,passenger_cars,commercial_vehicles,total
Germany,2023,3200000,400000,3600000
Germany,2022,3100000,380000,3480000
France,2023,1800000,250000,2050000
United States,2023,8500000,1200000,9700000
"""


class TestOicaParseResult:
    def _make_input(self, country: str = "", year: str = "") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"country": country, "year": year},
        )

    def test_successful_query_all(self):
        from openquery.sources.intl.oica import OicaSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_OICA_CSV
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = OicaSource()
            result = source.query(self._make_input())

        assert len(result.data) == 4
        assert result.total_countries == 3  # Germany, France, United States

    def test_country_filter(self):
        from openquery.sources.intl.oica import OicaSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_OICA_CSV
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = OicaSource()
            result = source.query(self._make_input(country="GERMANY"))

        assert len(result.data) == 2
        for row in result.data:
            assert "Germany" in row.country

    def test_year_filter(self):
        from openquery.sources.intl.oica import OicaSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_OICA_CSV
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = OicaSource()
            result = source.query(self._make_input(year="2023"))

        assert len(result.data) == 3
        for row in result.data:
            assert row.year == "2023"

    def test_country_and_year_filter(self):
        from openquery.sources.intl.oica import OicaSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_OICA_CSV
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = OicaSource()
            result = source.query(self._make_input(country="GERMANY", year="2023"))

        assert len(result.data) == 1
        assert result.data[0].country == "Germany"
        assert result.data[0].year == "2023"
        assert result.data[0].total == 3600000

    def test_total_computed_when_missing(self):
        from openquery.sources.intl.oica import OicaSource

        csv_no_total = (
            "country,year,passenger_cars,commercial_vehicles\nBrazil,2023,2000000,500000\n"
        )
        mock_resp = MagicMock()
        mock_resp.text = csv_no_total
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = OicaSource()
            result = source.query(self._make_input())

        assert result.data[0].total == 2500000

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.oica import OicaSource

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = OicaSource()
            with pytest.raises(SourceError, match="intl.oica"):
                source.query(self._make_input())

    def test_safe_int(self):
        from openquery.sources.intl.oica import _safe_int

        assert _safe_int("3,200,000") == 3200000
        assert _safe_int("0") == 0
        assert _safe_int("") == 0
        assert _safe_int("abc") == 0
