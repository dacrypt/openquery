"""Unit tests for us.sec_edgar — SEC EDGAR company filings source."""

from __future__ import annotations

from openquery.models.us.sec_edgar import SecEdgarFiling, SecEdgarResult
from openquery.sources.us.sec_edgar import SecEdgarSource


class TestSecEdgarResult:
    """Test SecEdgarResult model."""

    def test_default_values(self):
        data = SecEdgarResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.cik == ""
        assert data.total_filings == 0
        assert data.filings == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SecEdgarResult(
            search_term="Apple",
            company_name="Apple Inc.",
            cik="0000320193",
            total_filings=5,
            filings=[
                SecEdgarFiling(
                    filing_type="10-K",
                    date="2024-11-01",
                    description="Annual report",
                    url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123",
                )
            ],
        )
        json_str = data.model_dump_json()
        restored = SecEdgarResult.model_validate_json(json_str)
        assert restored.search_term == "Apple"
        assert restored.company_name == "Apple Inc."
        assert restored.cik == "0000320193"
        assert restored.total_filings == 5
        assert len(restored.filings) == 1
        assert restored.filings[0].filing_type == "10-K"

    def test_audit_excluded_from_json(self):
        data = SecEdgarResult(search_term="Apple", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSecEdgarFiling:
    """Test SecEdgarFiling model."""

    def test_default_values(self):
        f = SecEdgarFiling()
        assert f.filing_type == ""
        assert f.date == ""
        assert f.description == ""
        assert f.url == ""


class TestSecEdgarSourceMeta:
    """Test SecEdgarSource metadata."""

    def test_meta_name(self):
        source = SecEdgarSource()
        assert source.meta().name == "us.sec_edgar"

    def test_meta_country(self):
        source = SecEdgarSource()
        assert source.meta().country == "US"

    def test_meta_rate_limit(self):
        source = SecEdgarSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = SecEdgarSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = SecEdgarSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = SecEdgarSource()
        assert source._timeout == 30.0


class TestParseResponse:
    """Test _parse_response parsing logic."""

    def test_parse_valid_response(self):
        source = SecEdgarSource()
        data = {
            "hits": {
                "total": {"value": 3},
                "hits": [
                    {
                        "_source": {
                            "entity_name": "Apple Inc.",
                            "entity_id": "0000320193",
                            "file_type": "10-K",
                            "file_date": "2024-11-01",
                            "description": "Annual report",
                        }
                    },
                    {
                        "_source": {
                            "entity_name": "Apple Inc.",
                            "entity_id": "0000320193",
                            "file_type": "10-Q",
                            "file_date": "2024-08-01",
                            "description": "Quarterly report",
                        }
                    },
                ],
            }
        }
        result = source._parse_response("Apple", data)
        assert result.search_term == "Apple"
        assert result.company_name == "Apple Inc."
        assert result.cik == "0000320193"
        assert result.total_filings == 3
        assert len(result.filings) == 2
        assert result.filings[0].filing_type == "10-K"

    def test_parse_empty_hits(self):
        source = SecEdgarSource()
        data = {"hits": {"total": {"value": 0}, "hits": []}}
        result = source._parse_response("NoCompany", data)
        assert result.total_filings == 0
        assert result.filings == []

    def test_parse_integer_total(self):
        source = SecEdgarSource()
        data = {"hits": {"total": 5, "hits": []}}
        result = source._parse_response("Test", data)
        assert result.total_filings == 5
