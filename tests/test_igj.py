"""Unit tests for Argentina IGJ source — Inspección General de Justicia."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.ar.igj import IgjResult
from openquery.sources.ar.igj import IgjSource


class TestIgjResult:
    """Test IgjResult model."""

    def test_default_values(self):
        data = IgjResult()
        assert data.search_term == ""
        assert data.company_name == ""
        assert data.registration_status == ""
        assert data.correlative_number == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = IgjResult(
            search_term="ACME SA",
            company_name="ACME SOCIEDAD ANONIMA",
            registration_status="ACTIVA",
            correlative_number="12345",
            details={"tipo": "SA"},
        )
        json_str = data.model_dump_json()
        restored = IgjResult.model_validate_json(json_str)
        assert restored.search_term == "ACME SA"
        assert restored.company_name == "ACME SOCIEDAD ANONIMA"
        assert restored.registration_status == "ACTIVA"
        assert restored.correlative_number == "12345"
        assert restored.details == {"tipo": "SA"}

    def test_audit_excluded_from_json(self):
        data = IgjResult(search_term="ACME SA", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestIgjSourceMeta:
    """Test IgjSource metadata."""

    def test_meta_name(self):
        source = IgjSource()
        assert source.meta().name == "ar.igj"

    def test_meta_country(self):
        source = IgjSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = IgjSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = IgjSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = IgjSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = IgjSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs

    def test_default_timeout(self):
        source = IgjSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = IgjSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic."""

    def _make_page(self, body_text: str, rows: list[tuple[str, str]] | None = None):
        page = MagicMock()
        page.inner_text.return_value = body_text

        mock_rows = []
        for label, value in rows or []:
            row = MagicMock()
            td_label = MagicMock()
            td_label.inner_text.return_value = label
            td_value = MagicMock()
            td_value.inner_text.return_value = value
            row.query_selector_all.return_value = [td_label, td_value]
            mock_rows.append(row)

        page.query_selector_all.return_value = mock_rows
        return page

    def test_parse_from_table(self):
        source = IgjSource()
        page = self._make_page(
            "",
            rows=[
                ("Denominacion", "EMPRESA SA"),
                ("Estado", "ACTIVA"),
                ("Correlativo", "99999"),
            ],
        )
        result = source._parse_result(page, "EMPRESA SA")
        assert result.company_name == "EMPRESA SA"
        assert result.registration_status == "ACTIVA"
        assert result.correlative_number == "99999"

    def test_parse_from_body_text(self):
        source = IgjSource()
        body = "Denominacion: EMPRESA SRL\nEstado: INACTIVA\nCorrelativo: 55555"
        page = self._make_page(body)
        result = source._parse_result(page, "EMPRESA SRL")
        assert result.company_name == "EMPRESA SRL"
        assert result.registration_status == "INACTIVA"

    def test_parse_no_results(self):
        source = IgjSource()
        page = self._make_page("No se encontraron resultados")
        result = source._parse_result(page, "NONEXISTENT")
        assert result.search_term == "NONEXISTENT"
        assert result.company_name == ""
        assert result.registration_status == ""
