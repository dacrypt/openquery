"""Unit tests for us.treasury_ofac_sdn — Treasury OFAC SDN list."""

from __future__ import annotations

from openquery.models.us.treasury_ofac_sdn import SdnEntry, TreasuryOfacSdnResult
from openquery.sources.us.treasury_ofac_sdn import TreasuryOfacSdnSource


class TestTreasuryOfacSdnResult:
    def test_default_values(self):
        data = TreasuryOfacSdnResult()
        assert data.search_term == ""
        assert data.total == 0
        assert data.sdn_entries == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = TreasuryOfacSdnResult(
            search_term="TEST ENTITY",
            total=1,
            sdn_entries=[
                SdnEntry(
                    uid="12345",
                    name="TEST ENTITY",
                    sdn_type="SDN",
                    programs=["CUBA"],
                    remarks="Test remarks",
                )
            ],
        )
        restored = TreasuryOfacSdnResult.model_validate_json(data.model_dump_json())
        assert restored.total == 1
        assert restored.sdn_entries[0].uid == "12345"
        assert restored.sdn_entries[0].programs == ["CUBA"]

    def test_audit_excluded_from_json(self):
        data = TreasuryOfacSdnResult(search_term="test", audit={"x": 1})
        assert "audit" not in data.model_dump_json()

    def test_sdn_entry_defaults(self):
        entry = SdnEntry()
        assert entry.uid == ""
        assert entry.name == ""
        assert entry.sdn_type == ""
        assert entry.programs == []
        assert entry.remarks == ""


class TestTreasuryOfacSdnSourceMeta:
    def test_meta_name(self):
        assert TreasuryOfacSdnSource().meta().name == "us.treasury_ofac_sdn"

    def test_meta_country(self):
        assert TreasuryOfacSdnSource().meta().country == "US"

    def test_meta_requires_browser(self):
        assert TreasuryOfacSdnSource().meta().requires_browser is False

    def test_meta_requires_captcha(self):
        assert TreasuryOfacSdnSource().meta().requires_captcha is False

    def test_meta_rate_limit(self):
        assert TreasuryOfacSdnSource().meta().rate_limit_rpm == 10

    def test_default_timeout(self):
        assert TreasuryOfacSdnSource()._timeout == 60.0
