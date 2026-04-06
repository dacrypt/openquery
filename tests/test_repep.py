"""Unit tests for mx.repep — Mexico do-not-call registry source."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.mx.repep import RepepResult
from openquery.sources.mx.repep import RepepSource


class TestRepepResult:
    """Test RepepResult model."""

    def test_default_values(self):
        data = RepepResult()
        assert data.phone_number == ""
        assert data.is_registered is False
        assert data.registration_date == ""
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = RepepResult(
            phone_number="5512345678",
            is_registered=True,
            registration_date="2023-01-15",
            details={"raw_text": "Registrado"},
        )
        json_str = data.model_dump_json()
        restored = RepepResult.model_validate_json(json_str)
        assert restored.phone_number == "5512345678"
        assert restored.is_registered is True
        assert restored.registration_date == "2023-01-15"

    def test_audit_excluded_from_json(self):
        data = RepepResult(phone_number="5512345678", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestRepepSourceMeta:
    """Test RepepSource metadata."""

    def test_meta_name(self):
        source = RepepSource()
        assert source.meta().name == "mx.repep"

    def test_meta_country(self):
        source = RepepSource()
        assert source.meta().country == "MX"

    def test_meta_rate_limit(self):
        source = RepepSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_requires_browser(self):
        source = RepepSource()
        assert source.meta().requires_browser is True

    def test_meta_requires_captcha(self):
        source = RepepSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = RepepSource()
        assert source._timeout == 30.0

    def test_custom_timeout(self):
        source = RepepSource(timeout=60.0)
        assert source._timeout == 60.0


class TestParseResult:
    """Test _parse_result parsing logic with mocked page."""

    def _make_page(self, body_text: str) -> MagicMock:
        mock_page = MagicMock()
        mock_page.inner_text.return_value = body_text
        return mock_page

    def test_parse_registered(self):
        source = RepepSource()
        page = self._make_page(
            "Consulta REPEP\n"
            "El número 5512345678 está registrado en el REPEP.\n"
            "Fecha de inscripción: 15/01/2023\n"
        )
        result = source._parse_result(page, "5512345678")
        assert result.phone_number == "5512345678"
        assert result.is_registered is True
        assert result.registration_date == "15/01/2023"

    def test_parse_not_registered(self):
        source = RepepSource()
        page = self._make_page(
            "Consulta REPEP\n"
            "El número 5512345678 no está registrado en el REPEP.\n"
        )
        result = source._parse_result(page, "5512345678")
        assert result.is_registered is False

    def test_parse_phone_preserved(self):
        source = RepepSource()
        page = self._make_page("Sin resultados.")
        result = source._parse_result(page, "5599887766")
        assert result.phone_number == "5599887766"

    def test_parse_details_raw_text(self):
        source = RepepSource()
        page = self._make_page("Consulta REPEP\nRegistrado.")
        result = source._parse_result(page, "5512345678")
        assert "raw_text" in result.details
