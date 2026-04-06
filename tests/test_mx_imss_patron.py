"""Tests for mx.imss_patron — IMSS employer registry lookup."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from openquery.sources.base import DocumentType, QueryInput


class TestImssPatronResult:
    """Test ImssPatronResult model defaults and JSON roundtrip."""

    def test_defaults(self):
        from openquery.models.mx.imss_patron import ImssPatronResult

        r = ImssPatronResult()
        assert r.registro_patronal == ""
        assert r.employer_name == ""
        assert r.status == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        from openquery.models.mx.imss_patron import ImssPatronResult

        r = ImssPatronResult(registro_patronal="Y1234567890", audit={"data": "x"})
        dumped = r.model_dump_json()
        assert "audit" not in dumped
        assert "Y1234567890" in dumped

    def test_json_roundtrip(self):
        from openquery.models.mx.imss_patron import ImssPatronResult

        r = ImssPatronResult(
            registro_patronal="Y1234567890",
            employer_name="EMPRESA SA DE CV",
            status="Vigente",
            details={"Estatus": "Vigente"},
        )
        r2 = ImssPatronResult.model_validate_json(r.model_dump_json())
        assert r2.registro_patronal == "Y1234567890"
        assert r2.employer_name == "EMPRESA SA DE CV"
        assert r2.status == "Vigente"

    def test_queried_at_default(self):
        from openquery.models.mx.imss_patron import ImssPatronResult

        before = datetime.now()
        r = ImssPatronResult()
        after = datetime.now()
        assert before <= r.queried_at <= after


class TestImssPatronSourceMeta:
    """Test mx.imss_patron source metadata."""

    def test_meta_name(self):
        from openquery.sources.mx.imss_patron import ImssPatronSource

        assert ImssPatronSource().meta().name == "mx.imss_patron"

    def test_meta_country(self):
        from openquery.sources.mx.imss_patron import ImssPatronSource

        assert ImssPatronSource().meta().country == "MX"

    def test_meta_requires_browser(self):
        from openquery.sources.mx.imss_patron import ImssPatronSource

        assert ImssPatronSource().meta().requires_browser is True

    def test_meta_supported_inputs(self):
        from openquery.sources.mx.imss_patron import ImssPatronSource

        assert DocumentType.CUSTOM in ImssPatronSource().meta().supported_inputs

    def test_meta_rate_limit(self):
        from openquery.sources.mx.imss_patron import ImssPatronSource

        assert ImssPatronSource().meta().rate_limit_rpm == 10


class TestImssPatronParseResult:
    """Test _parse_result with mocked page."""

    def _parse(self, body_text: str, registro: str = "Y1234567890"):
        from openquery.sources.mx.imss_patron import ImssPatronSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        return ImssPatronSource()._parse_result(page, registro)

    def test_registro_patronal_preserved(self):
        assert self._parse("Datos").registro_patronal == "Y1234567890"

    def test_employer_name_parsed(self):
        result = self._parse("Razón social: EMPRESA SA DE CV\nOtros")
        assert result.employer_name == "EMPRESA SA DE CV"

    def test_status_parsed(self):
        result = self._parse("Estado: Vigente\nOtros")
        assert result.status == "Vigente"

    def test_empty_body(self):
        result = self._parse("")
        assert result.registro_patronal == "Y1234567890"
        assert result.employer_name == ""

    def test_query_missing_registro_raises(self):
        from openquery.exceptions import SourceError
        from openquery.sources.mx.imss_patron import ImssPatronSource

        with pytest.raises(SourceError, match="[Ee]mployer"):
            ImssPatronSource().query(
                QueryInput(document_type=DocumentType.CUSTOM, document_number="")
            )
