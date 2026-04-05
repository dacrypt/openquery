"""Tests for us.nhtsa_safety_ratings — NHTSA NCAP crash test safety ratings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# Model tests
# ===========================================================================

class TestNhtsaSafetyRatingsResult:
    def test_default_values(self):
        from openquery.models.us.nhtsa_safety_ratings import NhtsaSafetyRatingsResult
        r = NhtsaSafetyRatingsResult()
        assert r.make == ""
        assert r.model == ""
        assert r.model_year == ""
        assert r.ratings == []
        assert r.queried_at is not None

    def test_json_roundtrip(self):
        from openquery.models.us.nhtsa_safety_ratings import NhtsaSafetyRatingsResult
        r = NhtsaSafetyRatingsResult(make="Toyota", model="Camry", model_year="2024")
        data = r.model_dump_json()
        r2 = NhtsaSafetyRatingsResult.model_validate_json(data)
        assert r2.make == "Toyota"
        assert r2.model == "Camry"
        assert r2.model_year == "2024"

    def test_audit_excluded_from_json(self):
        from openquery.models.us.nhtsa_safety_ratings import NhtsaSafetyRatingsResult
        r = NhtsaSafetyRatingsResult(audit={"screenshot": "base64data"})
        data = r.model_dump_json()
        assert "audit" not in data
        assert "screenshot" not in data

    def test_ratings_list(self):
        from openquery.models.us.nhtsa_safety_ratings import (
            NhtsaSafetyRating,
            NhtsaSafetyRatingsResult,
        )
        rating = NhtsaSafetyRating(vehicle_id=19427, overall_rating="5")
        r = NhtsaSafetyRatingsResult(make="Toyota", ratings=[rating])
        assert len(r.ratings) == 1
        assert r.ratings[0].vehicle_id == 19427
        assert r.ratings[0].overall_rating == "5"


class TestNhtsaSafetyRating:
    def test_default_values(self):
        from openquery.models.us.nhtsa_safety_ratings import NhtsaSafetyRating
        r = NhtsaSafetyRating()
        assert r.vehicle_id == 0
        assert r.vehicle_description == ""
        assert r.overall_rating == ""
        assert r.rollover_probability == 0.0
        assert r.complaints_count == 0
        assert r.recalls_count == 0
        assert r.investigation_count == 0

    def test_json_roundtrip(self):
        from openquery.models.us.nhtsa_safety_ratings import NhtsaSafetyRating
        r = NhtsaSafetyRating(
            vehicle_id=19427,
            vehicle_description="2024 Toyota CAMRY 4 DR AWD",
            overall_rating="5",
            rollover_probability=0.12,
            complaints_count=3,
        )
        data = r.model_dump_json()
        r2 = NhtsaSafetyRating.model_validate_json(data)
        assert r2.vehicle_id == 19427
        assert r2.overall_rating == "5"
        assert r2.rollover_probability == 0.12
        assert r2.complaints_count == 3


# ===========================================================================
# Source meta tests
# ===========================================================================

class TestNhtsaSafetyRatingsSourceMeta:
    def test_name(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        meta = NhtsaSafetyRatingsSource().meta()
        assert meta.name == "us.nhtsa_safety_ratings"

    def test_country(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        meta = NhtsaSafetyRatingsSource().meta()
        assert meta.country == "US"

    def test_supported_inputs(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        meta = NhtsaSafetyRatingsSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_no_browser_no_captcha(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        meta = NhtsaSafetyRatingsSource().meta()
        assert meta.requires_browser is False
        assert meta.requires_captcha is False

    def test_rate_limit(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        meta = NhtsaSafetyRatingsSource().meta()
        assert meta.rate_limit_rpm == 20


# ===========================================================================
# Parse / query logic tests
# ===========================================================================

_PATCH_CLIENT = "openquery.sources.us.nhtsa_safety_ratings.httpx.Client"


class TestParseResult:
    def _make_vehicles_response(self, results):
        mock = MagicMock()
        mock.json.return_value = {"Count": len(results), "Results": results}
        mock.raise_for_status.return_value = None
        return mock

    def _make_ratings_response(self, raw: dict):
        mock = MagicMock()
        mock.json.return_value = {"Count": 1, "Results": [raw]}
        mock.raise_for_status.return_value = None
        return mock

    def _query(self, vehicles_resp, ratings_resp):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"make": "Toyota", "model": "Camry", "year": "2024"},
        )
        client_mock = MagicMock()
        client_mock.__enter__ = MagicMock(return_value=client_mock)
        client_mock.__exit__ = MagicMock(return_value=False)
        client_mock.get.side_effect = [vehicles_resp, ratings_resp]
        with patch(_PATCH_CLIENT, return_value=client_mock):
            return src.query(inp)

    def test_single_vehicle_parsed(self):
        vehicles = [{"VehicleId": 19427, "VehicleDescription": "2024 Toyota CAMRY 4 DR AWD"}]
        raw_rating = {
            "OverallRating": "5",
            "OverallFrontCrashRating": "5",
            "FrontCrashDriversideRating": "5",
            "FrontCrashPassengersideRating": "5",
            "OverallSideCrashRating": "4",
            "SideCrashDriversideRating": "4",
            "SideCrashPassengersideRating": "4",
            "RolloverRating": "4",
            "RolloverPossibility": 0.11,
            "SidePoleCrashRating": "5",
            "dynamicTipResult": "Not Tested",
            "NHTSAElectronicStabilityControl": "Standard",
            "NHTSAForwardCollisionWarning": "Standard",
            "NHTSALaneDepartureWarning": "Standard",
            "ComplaintsCount": 2,
            "RecallsCount": 1,
            "InvestigationCount": 0,
        }
        result = self._query(
            self._make_vehicles_response(vehicles),
            self._make_ratings_response(raw_rating),
        )
        assert result.make == "Toyota"
        assert result.model == "Camry"
        assert result.model_year == "2024"
        assert len(result.ratings) == 1
        r = result.ratings[0]
        assert r.vehicle_id == 19427
        assert r.vehicle_description == "2024 Toyota CAMRY 4 DR AWD"
        assert r.overall_rating == "5"
        assert r.front_crash_rating == "5"
        assert r.side_crash_rating == "4"
        assert r.rollover_rating == "4"
        assert r.rollover_probability == 0.11
        assert r.side_pole_rating == "5"
        assert r.electronic_stability_control == "Standard"
        assert r.forward_collision_warning == "Standard"
        assert r.lane_departure_warning == "Standard"
        assert r.complaints_count == 2
        assert r.recalls_count == 1
        assert r.investigation_count == 0

    def test_no_vehicles_returns_empty_ratings(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"make": "Unknown", "model": "Ghost", "year": "1999"},
        )
        vehicles_resp = MagicMock()
        vehicles_resp.json.return_value = {"Count": 0, "Results": []}
        vehicles_resp.raise_for_status.return_value = None

        client_mock = MagicMock()
        client_mock.__enter__ = MagicMock(return_value=client_mock)
        client_mock.__exit__ = MagicMock(return_value=False)
        client_mock.get.return_value = vehicles_resp
        with patch(_PATCH_CLIENT, return_value=client_mock):
            result = src.query(inp)
        assert result.ratings == []

    def test_missing_make_raises(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"model": "Camry", "year": "2024"},
        )
        with pytest.raises(SourceError, match="required"):
            src.query(inp)

    def test_missing_model_raises(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"make": "Toyota", "year": "2024"},
        )
        with pytest.raises(SourceError, match="required"):
            src.query(inp)

    def test_missing_year_raises(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"make": "Toyota", "model": "Camry"},
        )
        with pytest.raises(SourceError, match="required"):
            src.query(inp)

    def test_wrong_document_type_raises(self):
        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(document_type=DocumentType.VIN, document_number="1HGCM82633A123456")
        with pytest.raises(SourceError, match="Unsupported"):
            src.query(inp)

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.us.nhtsa_safety_ratings import NhtsaSafetyRatingsSource
        src = NhtsaSafetyRatingsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"make": "Toyota", "model": "Camry", "year": "2024"},
        )
        client_mock = MagicMock()
        client_mock.__enter__ = MagicMock(return_value=client_mock)
        client_mock.__exit__ = MagicMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 503
        client_mock.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_response
        )
        with patch(_PATCH_CLIENT, return_value=client_mock):
            with pytest.raises(SourceError, match="HTTP 503"):
                src.query(inp)
