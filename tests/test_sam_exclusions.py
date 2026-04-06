"""Unit tests for us.sam_exclusions — SAM.gov excluded parties source."""

from __future__ import annotations

from openquery.models.us.sam_exclusions import SamExclusion, SamExclusionsResult
from openquery.sources.us.sam_exclusions import SamExclusionsSource


class TestSamExclusionsResult:
    """Test SamExclusionsResult model."""

    def test_default_values(self):
        data = SamExclusionsResult()
        assert data.search_term == ""
        assert data.total == 0
        assert data.exclusions == []
        assert data.audit is None

    def test_round_trip_json(self):
        data = SamExclusionsResult(
            search_term="Corrupt Corp",
            total=1,
            exclusions=[
                SamExclusion(
                    name="Corrupt Corp LLC",
                    entity_type="Business",
                    exclusion_type="Ineligible (Proceedings Pending)",
                    agency="Department of Defense",
                    date="2024-03-15",
                )
            ],
        )
        json_str = data.model_dump_json()
        restored = SamExclusionsResult.model_validate_json(json_str)
        assert restored.search_term == "Corrupt Corp"
        assert restored.total == 1
        assert len(restored.exclusions) == 1
        assert restored.exclusions[0].name == "Corrupt Corp LLC"
        assert restored.exclusions[0].agency == "Department of Defense"

    def test_audit_excluded_from_json(self):
        data = SamExclusionsResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSamExclusion:
    """Test SamExclusion model."""

    def test_default_values(self):
        excl = SamExclusion()
        assert excl.name == ""
        assert excl.entity_type == ""
        assert excl.exclusion_type == ""
        assert excl.agency == ""
        assert excl.date == ""


class TestSamExclusionsSourceMeta:
    """Test SamExclusionsSource metadata."""

    def test_meta_name(self):
        source = SamExclusionsSource()
        assert source.meta().name == "us.sam_exclusions"

    def test_meta_country(self):
        source = SamExclusionsSource()
        assert source.meta().country == "US"

    def test_meta_rate_limit(self):
        source = SamExclusionsSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = SamExclusionsSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = SamExclusionsSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = SamExclusionsSource()
        assert source._timeout == 30.0


class TestParseResponse:
    """Test _parse_response parsing logic."""

    def test_parse_valid_response(self):
        source = SamExclusionsSource()
        data = {
            "totalRecords": 2,
            "exclusionData": [
                {
                    "entityInformation": {
                        "entityName": "Corrupt Corp LLC",
                        "entityType": "Business",
                    },
                    "exclusionDetails": {
                        "exclusionType": "Ineligible (Proceedings Pending)",
                        "agencyName": "Department of Defense",
                        "activationDate": "2024-03-15",
                    },
                },
                {
                    "entityInformation": {
                        "entityName": "John Doe",
                        "entityType": "Individual",
                    },
                    "exclusionDetails": {
                        "exclusionType": "Prohibition/Restriction",
                        "agencyName": "GSA",
                        "activationDate": "2023-11-01",
                    },
                },
            ],
        }
        result = source._parse_response("Corrupt", data)
        assert result.search_term == "Corrupt"
        assert result.total == 2
        assert len(result.exclusions) == 2
        assert result.exclusions[0].name == "Corrupt Corp LLC"
        assert result.exclusions[0].entity_type == "Business"
        assert result.exclusions[0].agency == "Department of Defense"
        assert result.exclusions[1].name == "John Doe"

    def test_parse_empty_response(self):
        source = SamExclusionsSource()
        data = {"totalRecords": 0, "exclusionData": []}
        result = source._parse_response("Nobody", data)
        assert result.total == 0
        assert result.exclusions == []

    def test_parse_fallback_legal_name(self):
        source = SamExclusionsSource()
        data = {
            "totalRecords": 1,
            "exclusionData": [
                {
                    "entityInformation": {
                        "legalBusinessName": "Fallback Name LLC",
                        "entityType": "Business",
                    },
                    "exclusionDetails": {
                        "exclusionType": "Debarred",
                        "ctCode": "DOD",
                        "creationDate": "2024-01-01",
                    },
                }
            ],
        }
        result = source._parse_response("Fallback", data)
        assert result.exclusions[0].name == "Fallback Name LLC"
        assert result.exclusions[0].agency == "DOD"
        assert result.exclusions[0].date == "2024-01-01"
