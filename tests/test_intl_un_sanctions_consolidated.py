"""Tests for intl.un_sanctions_consolidated — UN Consolidated Sanctions source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestUnSanctionsConsolidatedSourceMeta:
    def test_meta(self):
        from openquery.sources.intl.un_sanctions_consolidated import UnSanctionsConsolidatedSource
        meta = UnSanctionsConsolidatedSource().meta()
        assert meta.name == "intl.un_sanctions_consolidated"
        assert meta.country == "INTL"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_empty_name_raises(self):
        from openquery.sources.intl.un_sanctions_consolidated import UnSanctionsConsolidatedSource
        src = UnSanctionsConsolidatedSource()
        with pytest.raises(SourceError, match="[Nn]ame"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestUnSanctionsConsolidatedModel:
    def test_model_defaults(self):
        from openquery.models.intl.un_sanctions_consolidated import UnSanctionsConsolidatedResult
        r = UnSanctionsConsolidatedResult(search_term="Al-Qaeda")
        assert r.search_term == "Al-Qaeda"
        assert r.total == 0
        assert r.entries == []

    def test_model_with_entries(self):
        from openquery.models.intl.un_sanctions_consolidated import (
            UnSanctionEntry,
            UnSanctionsConsolidatedResult,
        )
        entry = UnSanctionEntry(name="Test Person", entity_type="individual", list_type="UN")
        r = UnSanctionsConsolidatedResult(search_term="Test", total=1, entries=[entry])
        data = r.model_dump_json()
        r2 = UnSanctionsConsolidatedResult.model_validate_json(data)
        assert r2.total == 1
        assert r2.entries[0].name == "Test Person"

    def test_audit_excluded(self):
        from openquery.models.intl.un_sanctions_consolidated import UnSanctionsConsolidatedResult
        r = UnSanctionsConsolidatedResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
