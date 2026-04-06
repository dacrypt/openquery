"""Tests for intl.eu_sanctions — EU Consolidated Financial Sanctions List.

Uses mocked httpx to avoid downloading the real XML.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestEuSanctionsResult — model tests
# ===========================================================================


class TestEuSanctionsResult:
    def test_defaults(self):
        from openquery.models.intl.eu_sanctions import EuSanctionsResult

        r = EuSanctionsResult()
        assert r.search_term == ""
        assert r.total == 0
        assert r.entries == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.eu_sanctions import EuSanctionEntry, EuSanctionsResult

        r = EuSanctionsResult(
            search_term="Putin",
            total=1,
            entries=[
                EuSanctionEntry(
                    name="PUTIN Vladimir Vladimirovich",
                    entity_type="person",
                    program="UKRAINE",
                    listed_date="2022-03-01",
                    details="President of Russian Federation",
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = EuSanctionsResult.model_validate_json(dumped)
        assert restored.search_term == "Putin"
        assert restored.total == 1
        assert restored.entries[0].name == "PUTIN Vladimir Vladimirovich"
        assert restored.entries[0].program == "UKRAINE"

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.eu_sanctions import EuSanctionsResult

        r = EuSanctionsResult(audit={"raw": "xml"})
        data = r.model_dump()
        assert "audit" not in data

    def test_entry_defaults(self):
        from openquery.models.intl.eu_sanctions import EuSanctionEntry

        e = EuSanctionEntry()
        assert e.name == ""
        assert e.entity_type == ""
        assert e.program == ""
        assert e.listed_date == ""
        assert e.details == ""


# ===========================================================================
# TestEuSanctionsSourceMeta
# ===========================================================================


class TestEuSanctionsSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        meta = EuSanctionsSource().meta()
        assert meta.name == "intl.eu_sanctions"

    def test_meta_country(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        meta = EuSanctionsSource().meta()
        assert meta.country == "INTL"

    def test_meta_no_captcha(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        meta = EuSanctionsSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        meta = EuSanctionsSource().meta()
        assert meta.rate_limit_rpm == 5

    def test_meta_supports_custom(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        meta = EuSanctionsSource().meta()
        assert DocumentType.CUSTOM in meta.supported_inputs


# ===========================================================================
# TestEuSanctionsParseResult
# ===========================================================================

# Minimal EU FSF XML with two entities matching "Putin" and one not matching
MOCK_EU_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<export>
  <sanctionEntity subjectType="person">
    <nameAlias wholeName="PUTIN Vladimir Vladimirovich" />
    <regulation programme="UKRAINE" entryIntoForceDate="2022-03-01" />
    <remark>President of Russian Federation</remark>
  </sanctionEntity>
  <sanctionEntity subjectType="person">
    <nameAlias wholeName="MEDVEDEV Dmitry" />
    <regulation programme="UKRAINE" entryIntoForceDate="2022-03-01" />
  </sanctionEntity>
  <sanctionEntity subjectType="entity">
    <nameAlias wholeName="PUTIN CONSULTING GROUP" />
    <regulation programme="UKRAINE" entryIntoForceDate="2023-01-15" />
  </sanctionEntity>
</export>
"""


class TestEuSanctionsParseResult:
    def _make_input(self, name: str = "Putin") -> QueryInput:
        return QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={"name": name},
        )

    def test_successful_search_finds_matches(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        mock_resp = MagicMock()
        mock_resp.content = MOCK_EU_XML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EuSanctionsSource()
            result = source.query(self._make_input("Putin"))

        assert result.search_term == "Putin"
        assert result.total == 2
        assert len(result.entries) == 2
        names = [e.name for e in result.entries]
        assert "PUTIN Vladimir Vladimirovich" in names
        assert "PUTIN CONSULTING GROUP" in names

    def test_search_no_matches(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        mock_resp = MagicMock()
        mock_resp.content = MOCK_EU_XML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EuSanctionsSource()
            result = source.query(self._make_input("Nonexistent Person"))

        assert result.total == 0
        assert result.entries == []

    def test_search_via_document_number(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        mock_resp = MagicMock()
        mock_resp.content = MOCK_EU_XML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EuSanctionsSource()
            inp = QueryInput(
                document_number="Medvedev",
                document_type=DocumentType.CUSTOM,
                extra={},
            )
            result = source.query(inp)

        assert result.search_term == "Medvedev"
        assert result.total == 1
        assert result.entries[0].name == "MEDVEDEV Dmitry"

    def test_missing_input_raises(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        source = EuSanctionsSource()
        inp = QueryInput(
            document_number="",
            document_type=DocumentType.CUSTOM,
            extra={},
        )
        with pytest.raises(SourceError, match="intl.eu_sanctions"):
            source.query(inp)

    def test_entry_program_and_date(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        mock_resp = MagicMock()
        mock_resp.content = MOCK_EU_XML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EuSanctionsSource()
            result = source.query(self._make_input("Putin Vladimir"))

        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.program == "UKRAINE"
        assert entry.listed_date == "2022-03-01"
        assert entry.entity_type == "person"
        assert "President" in entry.details

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EuSanctionsSource()
            with pytest.raises(SourceError, match="intl.eu_sanctions"):
                source.query(self._make_input())

    def test_xml_parse_error_raises_source_error(self):
        from openquery.sources.intl.eu_sanctions import EuSanctionsSource

        mock_resp = MagicMock()
        mock_resp.content = b"NOT VALID XML <<<"
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            source = EuSanctionsSource()
            with pytest.raises(SourceError, match="intl.eu_sanctions"):
                source.query(self._make_input())
