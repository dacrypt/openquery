"""Unit tests for us.nhtsa_investigations — NHTSA ODI defect investigations."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.models.us.nhtsa_investigations import NhtsaInvestigation, NhtsaInvestigationsResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.us.nhtsa_investigations import NhtsaInvestigationsSource


# ── Model tests ──────────────────────────────────────────────────────────────


class TestNhtsaInvestigationsResult:
    def test_default_values(self):
        r = NhtsaInvestigationsResult()
        assert r.make == ""
        assert r.model == ""
        assert r.model_year == ""
        assert r.total == 0
        assert r.investigations == []
        assert isinstance(r.queried_at, datetime)

    def test_round_trip(self):
        r = NhtsaInvestigationsResult(
            make="FORD",
            model="EXPLORER",
            model_year="2022",
            total=2,
            investigations=[
                NhtsaInvestigation(
                    nhtsa_id="12345",
                    investigation_number="PE22001",
                    investigation_type="PE",
                    subject="ENGINE STALL",
                    description="Vehicles may stall unexpectedly.",
                    status="Closed",
                    open_date="2022-01-15",
                    close_date="2022-06-30",
                    components=["ENGINE"],
                    make="FORD",
                    model="EXPLORER",
                    year="2022",
                )
            ],
        )
        restored = NhtsaInvestigationsResult.model_validate_json(r.model_dump_json())
        assert restored.make == "FORD"
        assert restored.model == "EXPLORER"
        assert restored.total == 2
        assert len(restored.investigations) == 1
        assert restored.investigations[0].investigation_number == "PE22001"
        assert restored.investigations[0].components == ["ENGINE"]

    def test_audit_excluded_from_dump(self):
        r = NhtsaInvestigationsResult(make="FORD", audit={"screenshot": "data"})
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_investigation_default_values(self):
        inv = NhtsaInvestigation()
        assert inv.nhtsa_id == ""
        assert inv.investigation_number == ""
        assert inv.investigation_type == ""
        assert inv.subject == ""
        assert inv.description == ""
        assert inv.status == ""
        assert inv.open_date == ""
        assert inv.close_date == ""
        assert inv.components == []
        assert inv.make == ""
        assert inv.model == ""
        assert inv.year == ""


# ── Source meta tests ─────────────────────────────────────────────────────────


class TestNhtsaInvestigationsSourceMeta:
    def test_name(self):
        src = NhtsaInvestigationsSource()
        assert src.meta().name == "us.nhtsa_investigations"

    def test_country(self):
        src = NhtsaInvestigationsSource()
        assert src.meta().country == "US"

    def test_supported_inputs(self):
        src = NhtsaInvestigationsSource()
        meta = src.meta()
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_no_browser_or_captcha(self):
        src = NhtsaInvestigationsSource()
        meta = src.meta()
        assert meta.requires_browser is False
        assert meta.requires_captcha is False

    def test_rate_limit(self):
        src = NhtsaInvestigationsSource()
        assert src.meta().rate_limit_rpm == 20


# ── Parse / query tests ───────────────────────────────────────────────────────


def _make_input(make: str = "FORD", model: str = "EXPLORER", year: str = "2022") -> QueryInput:
    return QueryInput(
        document_type=DocumentType.CUSTOM,
        document_number="",
        extra={"make": make, "model": model, "year": year},
    )


def _mock_response(results: list[dict], total: int | None = None) -> MagicMock:
    payload: dict = {"results": results}
    if total is not None:
        payload["meta"] = {"pagination": {"total": total}}
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestParseResult:
    def test_basic_parsing(self):
        raw = [
            {
                "nhtsaId": "ABC123",
                "investigationNumber": "PE22001",
                "investigationType": "PE",
                "subject": "ENGINE STALL",
                "description": "Vehicles may stall.",
                "status": "Closed",
                "openDate": "2022-01-15",
                "closeDate": "2022-06-30",
                "components": ["ENGINE", "FUEL SYSTEM"],
                "make": "FORD",
                "model": "EXPLORER",
                "year": "2022",
            }
        ]
        mock_resp = _mock_response(raw, total=1)

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            src = NhtsaInvestigationsSource()
            result = src.query(_make_input())

        assert isinstance(result, NhtsaInvestigationsResult)
        assert result.make == "FORD"
        assert result.model == "EXPLORER"
        assert result.model_year == "2022"
        assert result.total == 1
        assert len(result.investigations) == 1
        inv = result.investigations[0]
        assert inv.nhtsa_id == "ABC123"
        assert inv.investigation_number == "PE22001"
        assert inv.investigation_type == "PE"
        assert inv.subject == "ENGINE STALL"
        assert inv.status == "Closed"
        assert inv.components == ["ENGINE", "FUEL SYSTEM"]

    def test_html_stripped_from_description(self):
        raw = [
            {
                "nhtsaId": "X1",
                "investigationNumber": "EA23001",
                "investigationType": "EA",
                "subject": "FIRE RISK",
                "description": "<p>Risk of <b>fire</b> in engine compartment.</p>",
                "status": "Open",
                "openDate": "2023-03-01",
                "closeDate": "",
                "components": ["ENGINE"],
                "make": "TOYOTA",
                "model": "CAMRY",
                "year": "2023",
            }
        ]
        mock_resp = _mock_response(raw)

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            src = NhtsaInvestigationsSource()
            result = src.query(_make_input("TOYOTA", "CAMRY", "2023"))

        assert "<" not in result.investigations[0].description
        assert "Risk of fire in engine compartment." == result.investigations[0].description

    def test_empty_results(self):
        mock_resp = _mock_response([], total=0)

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            src = NhtsaInvestigationsSource()
            result = src.query(_make_input())

        assert result.total == 0
        assert result.investigations == []

    def test_total_from_pagination(self):
        raw = [{"nhtsaId": "1", "investigationNumber": "DP21001", "investigationType": "DP",
                "subject": "BRAKES", "description": "Brake issue.", "status": "Open",
                "openDate": "2021-05-01", "closeDate": "", "components": ["BRAKES"],
                "make": "HONDA", "model": "ACCORD", "year": "2021"}]
        mock_resp = _mock_response(raw, total=42)

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            src = NhtsaInvestigationsSource()
            result = src.query(_make_input("HONDA", "ACCORD", "2021"))

        assert result.total == 42

    def test_missing_make_raises_source_error(self):
        from openquery.exceptions import SourceError

        src = NhtsaInvestigationsSource()
        inp = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"model": "EXPLORER", "year": "2022"},
        )
        with pytest.raises(SourceError, match="make, model, and year are required"):
            src.query(inp)

    def test_wrong_document_type_raises_source_error(self):
        from openquery.exceptions import SourceError

        src = NhtsaInvestigationsSource()
        inp = QueryInput(
            document_type=DocumentType.VIN,
            document_number="1HGBH41JXMN109186",
        )
        with pytest.raises(SourceError, match="Unsupported input type"):
            src.query(inp)

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.exceptions import SourceError

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.status_code = 503
            mock_client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
                "503", request=MagicMock(), response=MagicMock(status_code=503)
            )

            src = NhtsaInvestigationsSource()
            with pytest.raises(SourceError, match="API returned HTTP"):
                src.query(_make_input())
