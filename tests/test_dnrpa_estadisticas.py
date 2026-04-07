"""Tests for ar.dnrpa_estadisticas — DNRPA vehicle registration statistics."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestDnrpaEstadisticasResult — model tests
# ===========================================================================


class TestDnrpaEstadisticasResult:
    def test_defaults(self):
        from openquery.models.ar.dnrpa_estadisticas import DnrpaEstadisticasResult

        r = DnrpaEstadisticasResult()
        assert r.search_term == ""
        assert r.total_records == 0
        assert r.estadisticas == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.ar.dnrpa_estadisticas import DnrpaEstadistica, DnrpaEstadisticasResult

        r = DnrpaEstadisticasResult(
            search_term="2023",
            total_records=2,
            estadisticas=[
                DnrpaEstadistica(
                    year="2023",
                    month="01",
                    province="Buenos Aires",
                    tramite_type="Inscripcion",
                    quantity=1500,
                ),
                DnrpaEstadistica(
                    year="2023",
                    month="02",
                    province="Cordoba",
                    tramite_type="Transferencia",
                    quantity=800,
                ),
            ],
        )
        dumped = r.model_dump_json()
        restored = DnrpaEstadisticasResult.model_validate_json(dumped)
        assert restored.search_term == "2023"
        assert len(restored.estadisticas) == 2
        assert restored.estadisticas[0].quantity == 1500

    def test_audit_excluded_from_json(self):
        from openquery.models.ar.dnrpa_estadisticas import DnrpaEstadisticasResult

        r = DnrpaEstadisticasResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_estadistica_defaults(self):
        from openquery.models.ar.dnrpa_estadisticas import DnrpaEstadistica

        e = DnrpaEstadistica()
        assert e.year == ""
        assert e.month == ""
        assert e.province == ""
        assert e.tramite_type == ""
        assert e.quantity == 0


# ===========================================================================
# TestDnrpaEstadisticasSourceMeta
# ===========================================================================


class TestDnrpaEstadisticasSourceMeta:
    def test_meta_name(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        meta = DnrpaEstadisticasSource().meta()
        assert meta.name == "ar.dnrpa_estadisticas"

    def test_meta_country(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        meta = DnrpaEstadisticasSource().meta()
        assert meta.country == "AR"

    def test_meta_no_captcha(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        meta = DnrpaEstadisticasSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_supports_custom(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        meta = DnrpaEstadisticasSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestDnrpaEstadisticasParseResult
# ===========================================================================

MOCK_CKAN_META = {
    "success": True,
    "result": {
        "resources": [
            {
                "format": "CSV",
                "url": "https://datos.gob.ar/dataset/tramites-2023.csv",
                "name": "tramites_automotores_2023",
            }
        ]
    },
}

MOCK_CSV_CONTENT = """anio,mes,provincia,tipo_tramite,cantidad
2023,01,Buenos Aires,Inscripcion,1500
2023,01,Cordoba,Inscripcion,800
2023,02,Buenos Aires,Transferencia,2000
2023,02,Cordoba,Transferencia,950
"""


class TestDnrpaEstadisticasParseResult:
    def _make_input(self, year: str = "2023", month: str = "") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"year": year, "month": month},
        )

    def _make_mock_client(self, meta_resp_data, csv_content: str) -> MagicMock:
        mock_meta_resp = MagicMock()
        mock_meta_resp.json.return_value = meta_resp_data
        mock_meta_resp.raise_for_status = MagicMock()

        mock_csv_resp = MagicMock()
        mock_csv_resp.text = csv_content
        mock_csv_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_meta_resp
            return mock_csv_resp

        mock_client.get.side_effect = side_effect
        return mock_client

    def test_successful_query_all_years(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        mock_client = self._make_mock_client(MOCK_CKAN_META, MOCK_CSV_CONTENT)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = DnrpaEstadisticasSource()
            result = source.query(self._make_input(year="2023"))

        assert result.total_records == 4
        assert result.estadisticas[0].province == "Buenos Aires"
        assert result.estadisticas[0].quantity == 1500

    def test_year_month_filter(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        mock_client = self._make_mock_client(MOCK_CKAN_META, MOCK_CSV_CONTENT)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = DnrpaEstadisticasSource()
            result = source.query(self._make_input(year="2023", month="01"))

        # Only January records
        assert result.total_records == 2
        for rec in result.estadisticas:
            assert rec.month == "01"

    def test_ckan_api_failure_raises(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        bad_meta = {"success": False, "error": {"message": "Not found"}}
        mock_client = self._make_mock_client(bad_meta, "")

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = DnrpaEstadisticasSource()
            with pytest.raises(SourceError, match="CKAN API error"):
                source.query(self._make_input())

    def test_no_csv_resource_raises(self):
        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        meta_no_csv = {"success": True, "result": {"resources": []}}
        mock_client = self._make_mock_client(meta_no_csv, "")

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            source = DnrpaEstadisticasSource()
            with pytest.raises(SourceError, match="No CSV resource"):
                source.query(self._make_input())

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.ar.dnrpa_estadisticas import DnrpaEstadisticasSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = DnrpaEstadisticasSource()
            with pytest.raises(SourceError, match="ar.dnrpa_estadisticas"):
                source.query(self._make_input())
