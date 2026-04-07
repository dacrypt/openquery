"""Tests for br.aneel_ev — ANEEL EV charging station registry.

Uses mocked httpx to avoid hitting the real API.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestAneelEvResult — model tests
# ===========================================================================


class TestAneelEvResult:
    def test_defaults(self):
        from openquery.models.br.aneel_ev import AneelEvResult

        r = AneelEvResult()
        assert r.search_params == ""
        assert r.total_stations == 0
        assert r.stations == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.br.aneel_ev import AneelEvResult, AneelEvStation

        r = AneelEvResult(
            search_params="state=SP",
            total_stations=1,
            stations=[
                AneelEvStation(
                    name="Posto Eletrico SP",
                    operator="EDP",
                    city="São Paulo",
                    state="SP",
                    power_kw="22",
                    connector_type="Tipo 2",
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = AneelEvResult.model_validate_json(dumped)
        assert restored.total_stations == 1
        assert restored.stations[0].name == "Posto Eletrico SP"
        assert restored.stations[0].state == "SP"

    def test_audit_excluded_from_json(self):
        from openquery.models.br.aneel_ev import AneelEvResult

        r = AneelEvResult(audit={"raw": "data"})
        data = r.model_dump()
        assert "audit" not in data

    def test_station_defaults(self):
        from openquery.models.br.aneel_ev import AneelEvStation

        s = AneelEvStation()
        assert s.name == ""
        assert s.operator == ""
        assert s.power_kw == ""
        assert s.public_access == ""


# ===========================================================================
# TestAneelEvSourceMeta
# ===========================================================================


class TestAneelEvSourceMeta:
    def test_meta_name(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        assert AneelEvSource().meta().name == "br.aneel_ev"

    def test_meta_country(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        assert AneelEvSource().meta().country == "BR"

    def test_meta_no_captcha(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        meta = AneelEvSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        assert AneelEvSource().meta().rate_limit_rpm == 10

    def test_meta_supports_custom(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        assert DocumentType.CUSTOM in AneelEvSource().meta().supported_inputs


# ===========================================================================
# TestAneelEvParseResult
# ===========================================================================

MOCK_PACKAGE_RESPONSE = {
    "result": {
        "resources": [
            {"id": "abc-123", "datastore_active": True, "name": "EV Stations"},
        ]
    }
}

MOCK_DATASTORE_RESPONSE = {
    "result": {
        "total": 1,
        "records": [
            {
                "NomEstacao": "EV Park SP",
                "NomEmpresa": "EDP Brasil",
                "DscEndereco": "Av. Paulista 1000",
                "NomMunicipio": "SAO PAULO",
                "SigUF": "SP",
                "VlrPotencia": "22",
                "DscConector": "Tipo 2",
                "DscAcessoPublico": "Sim",
            }
        ],
    }
}


class TestAneelEvParseResult:
    def _make_client(self, pkg_resp, ds_resp) -> MagicMock:
        mock_pkg = MagicMock()
        mock_pkg.json.return_value = pkg_resp
        mock_pkg.raise_for_status = MagicMock()

        mock_ds = MagicMock()
        mock_ds.json.return_value = ds_resp
        mock_ds.raise_for_status = MagicMock()

        mock_client = MagicMock()
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_pkg
            return mock_ds

        mock_client.get.side_effect = side_effect
        return mock_client

    def test_successful_query(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        mock_client = self._make_client(MOCK_PACKAGE_RESPONSE, MOCK_DATASTORE_RESPONSE)

        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client

            source = AneelEvSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={"state": "SP"},
            )
            result = source.query(inp)

        assert result.total_stations == 1
        assert result.stations[0].name == "EV Park SP"
        assert result.stations[0].operator == "EDP Brasil"
        assert result.stations[0].state == "SP"
        assert result.stations[0].connector_type == "Tipo 2"

    def test_no_filters_returns_all(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        mock_client = self._make_client(MOCK_PACKAGE_RESPONSE, MOCK_DATASTORE_RESPONSE)

        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client

            source = AneelEvSource()
            inp = QueryInput(
                document_number="",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.search_params == "all"

    def test_resource_id_cached(self):
        from openquery.sources.br.aneel_ev import AneelEvSource

        mock_client = self._make_client(MOCK_PACKAGE_RESPONSE, MOCK_DATASTORE_RESPONSE)

        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client

            source = AneelEvSource()
            # First call discovers resource_id
            source._fetch("SP", "", "")
            # Inject cached resource_id
            assert source._resource_id == "abc-123"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.br.aneel_ev import AneelEvSource

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="br.aneel_ev"):
                AneelEvSource().query(
                    QueryInput(
                        document_number="",
                        document_type=DocumentType.CUSTOM,
                        extra={},
                    )
                )
