"""Tests for pe.migraciones — Peru immigration status lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestMigracionesResult:
    """Test MigracionesResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.pe.migraciones import MigracionesResult

        r = MigracionesResult()
        assert r.document_number == ""
        assert r.immigration_status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.pe.migraciones import MigracionesResult

        r = MigracionesResult(document_number="AB123456", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "AB123456" in dumped

    def test_json_roundtrip(self):
        from openquery.models.pe.migraciones import MigracionesResult

        r = MigracionesResult(
            document_number="AB123456",
            immigration_status="Regular",
            details={"Estado migratorio": "Regular"},
        )
        r2 = MigracionesResult.model_validate_json(r.model_dump_json())
        assert r2.document_number == "AB123456"
        assert r2.immigration_status == "Regular"

    def test_queried_at_default(self):
        from openquery.models.pe.migraciones import MigracionesResult

        before = datetime.now()
        r = MigracionesResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestMigracionesSourceMeta:
    """Test pe.migraciones source metadata."""

    def test_meta_name(self):
        from openquery.sources.pe.migraciones import MigracionesSource

        assert MigracionesSource().meta().name == "pe.migraciones"

    def test_meta_country(self):
        from openquery.sources.pe.migraciones import MigracionesSource

        assert MigracionesSource().meta().country == "PE"

    def test_meta_requires_browser(self):
        from openquery.sources.pe.migraciones import MigracionesSource

        assert MigracionesSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.pe.migraciones import MigracionesSource

        assert DocumentType.CUSTOM in MigracionesSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.pe.migraciones import MigracionesSource

        assert MigracionesSource().meta().rate_limit_rpm == 10


class TestMigracionesParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, document_number: str = "AB123456"):
        from openquery.sources.pe.migraciones import MigracionesSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return MigracionesSource()._parse_result(page, document_number)

    def test_document_number_preserved(self):
        assert self._parse("Datos", document_number="CD789012").document_number == "CD789012"

    def test_immigration_status_parsed(self):
        result = self._parse("Estado migratorio: Regular\nOtros")
        assert result.immigration_status == "Regular"

    def test_empty_body(self):
        result = self._parse("")
        assert result.document_number == "AB123456"
        assert result.immigration_status == ""

    def test_query_missing_document_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.pe.migraciones import MigracionesSource

        with pytest.raises(SourceError, match="Document number"):
            MigracionesSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )
