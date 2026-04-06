"""Tests for intl.icij_offshore — ICIJ Offshore Leaks database source."""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestIcijOffshoreSourceMeta:
    def test_meta(self):
        from openquery.sources.intl.icij_offshore import IcijOffshoreSource
        meta = IcijOffshoreSource().meta()
        assert meta.name == "intl.icij_offshore"
        assert meta.country == "INTL"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_empty_name_raises(self):
        from openquery.sources.intl.icij_offshore import IcijOffshoreSource
        src = IcijOffshoreSource()
        with pytest.raises(SourceError, match="[Nn]ame"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


class TestIcijOffshoreModel:
    def test_model_defaults(self):
        from openquery.models.intl.icij_offshore import IcijOffshoreResult
        r = IcijOffshoreResult(search_term="Mossack Fonseca")
        assert r.search_term == "Mossack Fonseca"
        assert r.total == 0
        assert r.entities == []

    def test_model_with_entities(self):
        from openquery.models.intl.icij_offshore import IcijOffshoreEntity, IcijOffshoreResult
        entity = IcijOffshoreEntity(name="Shell Corp", entity_type="company", dataset="Panama Papers")  # noqa: E501
        r = IcijOffshoreResult(search_term="Shell", total=1, entities=[entity])
        data = r.model_dump_json()
        r2 = IcijOffshoreResult.model_validate_json(data)
        assert r2.total == 1
        assert r2.entities[0].dataset == "Panama Papers"

    def test_audit_excluded(self):
        from openquery.models.intl.icij_offshore import IcijOffshoreResult
        r = IcijOffshoreResult(search_term="test", audit=b"pdf")
        assert "audit" not in r.model_dump_json()
