"""Unit tests for new MX sources: mx.sat_rfc, mx.condusef, mx.profeco."""

from __future__ import annotations

from openquery.models.mx.condusef import CondusefResult
from openquery.models.mx.profeco import ProfecoResult
from openquery.models.mx.sat_rfc import SatRfcResult
from openquery.sources.mx.condusef import CondusefSource
from openquery.sources.mx.profeco import ProfecoSource
from openquery.sources.mx.sat_rfc import SatRfcSource

# ---------------------------------------------------------------------------
# mx.sat_rfc
# ---------------------------------------------------------------------------


class TestSatRfcResult:
    def test_default_values(self):
        r = SatRfcResult()
        assert r.rfc == ""
        assert r.taxpayer_name == ""
        assert r.rfc_status == ""
        assert r.registration_status == ""
        assert r.details == ""

    def test_round_trip(self):
        r = SatRfcResult(
            rfc="XAXX010101000",
            taxpayer_name="EMPRESA EJEMPLO SA DE CV",
            rfc_status="Activo",
            registration_status="2010-01-01",
        )
        restored = SatRfcResult.model_validate_json(r.model_dump_json())
        assert restored.rfc == "XAXX010101000"
        assert restored.taxpayer_name == "EMPRESA EJEMPLO SA DE CV"
        assert restored.rfc_status == "Activo"

    def test_audit_excluded(self):
        r = SatRfcResult(rfc="XAXX010101000")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped

    def test_json_audit_excluded(self):
        r = SatRfcResult(rfc="XAXX010101000")
        r.audit = b"pdf_bytes"
        import json

        data = json.loads(r.model_dump_json())
        assert "audit" not in data


class TestSatRfcSourceMeta:
    def test_meta(self):
        src = SatRfcSource()
        meta = src.meta()
        assert meta.name == "mx.sat_rfc"
        assert meta.country == "MX"
        assert meta.requires_captcha is True
        assert meta.rate_limit_rpm == 5
        assert meta.requires_browser is True

    def test_source_name_in_meta(self):
        src = SatRfcSource()
        meta = src.meta()
        assert "SAT" in meta.display_name
        assert "RFC" in meta.display_name


class TestSatRfcParseResult:
    def test_parse_not_found(self):
        """Source should return 'No registrado' status when RFC not found."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = "El RFC no existe en el padrón del SAT"

        src = SatRfcSource()
        result = src._parse_result(page, "XAXX010101000")

        assert result.rfc == "XAXX010101000"
        assert result.rfc_status == "No registrado"

    def test_parse_active_status(self):
        """Source should extract 'Activo' status when found in body text."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "RFC: XAXX010101000\n"
            "Denominación: EMPRESA EJEMPLO SA DE CV\n"
            "Situación: Activo\n"
            "Fecha de alta: 2010-01-01"
        )

        src = SatRfcSource()
        result = src._parse_result(page, "XAXX010101000")

        assert result.rfc == "XAXX010101000"
        assert result.rfc_status == "Activo"


# ---------------------------------------------------------------------------
# mx.condusef
# ---------------------------------------------------------------------------


class TestCondusefResult:
    def test_default_values(self):
        r = CondusefResult()
        assert r.institution_name == ""
        assert r.total_complaints == 0
        assert r.resolution_rate == ""
        assert r.products == []
        assert r.details == ""

    def test_round_trip(self):
        r = CondusefResult(
            institution_name="BBVA MEXICO",
            total_complaints=1500,
            resolution_rate="72.5%",
            products=["Tarjeta de crédito", "Crédito hipotecario"],
        )
        restored = CondusefResult.model_validate_json(r.model_dump_json())
        assert restored.institution_name == "BBVA MEXICO"
        assert restored.total_complaints == 1500
        assert restored.resolution_rate == "72.5%"
        assert len(restored.products) == 2

    def test_audit_excluded(self):
        r = CondusefResult(institution_name="BBVA MEXICO")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestCondusefSourceMeta:
    def test_meta(self):
        src = CondusefSource()
        meta = src.meta()
        assert meta.name == "mx.condusef"
        assert meta.country == "MX"
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10
        assert meta.requires_browser is True

    def test_display_name(self):
        src = CondusefSource()
        meta = src.meta()
        assert "CONDUSEF" in meta.display_name


class TestCondusefParseResult:
    def test_parse_complaint_count(self):
        """Source should extract total complaints from body text."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "BBVA MEXICO\nTotal de quejas: 1,500\nResolución favorable: 72.5%\n"
        )
        page.query_selector_all.return_value = []

        src = CondusefSource()
        result = src._parse_result(page, "BBVA MEXICO")

        assert result.institution_name == "BBVA MEXICO"
        assert result.total_complaints == 1500

    def test_parse_resolution_rate(self):
        """Source should extract resolution rate percentage."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = "Institución: HSBC\nResolución: 65.3%\nQuejas: 800 quejas"
        page.query_selector_all.return_value = []

        src = CondusefSource()
        result = src._parse_result(page, "HSBC")

        assert result.resolution_rate == "65.3%"


# ---------------------------------------------------------------------------
# mx.profeco
# ---------------------------------------------------------------------------


class TestProfecoResult:
    def test_default_values(self):
        r = ProfecoResult()
        assert r.provider_name == ""
        assert r.total_complaints == 0
        assert r.resolved == 0
        assert r.conciliation_rate == ""
        assert r.sector == ""
        assert r.details == ""

    def test_round_trip(self):
        r = ProfecoResult(
            provider_name="TELCEL",
            total_complaints=300,
            resolved=180,
            conciliation_rate="60.0%",
            sector="Telecomunicaciones",
        )
        restored = ProfecoResult.model_validate_json(r.model_dump_json())
        assert restored.provider_name == "TELCEL"
        assert restored.total_complaints == 300
        assert restored.resolved == 180
        assert restored.conciliation_rate == "60.0%"
        assert restored.sector == "Telecomunicaciones"

    def test_audit_excluded(self):
        r = ProfecoResult(provider_name="TELCEL")
        r.audit = {"evidence": "test"}
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestProfecoSourceMeta:
    def test_meta(self):
        src = ProfecoSource()
        meta = src.meta()
        assert meta.name == "mx.profeco"
        assert meta.country == "MX"
        assert meta.requires_captcha is False
        assert meta.rate_limit_rpm == 10
        assert meta.requires_browser is True

    def test_display_name(self):
        src = ProfecoSource()
        meta = src.meta()
        assert "Profeco" in meta.display_name


class TestProfecoParseResult:
    def test_parse_complaint_count(self):
        """Source should extract total complaints and resolved count."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "TELCEL\n"
            "Sector: Telecomunicaciones\n"
            "Total quejas: 300\n"
            "180 resueltos\n"
            "Conciliación: 60.0%\n"
        )

        src = ProfecoSource()
        result = src._parse_result(page, "TELCEL")

        assert result.provider_name == "TELCEL"
        assert result.total_complaints == 300

    def test_parse_sector(self):
        """Source should extract sector from body text."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "Empresa: CFE\nSector: Energía eléctrica\nQuejas: 500 quejas\n"
        )

        src = ProfecoSource()
        result = src._parse_result(page, "CFE")

        assert result.sector == "Energía eléctrica"

    def test_parse_conciliation_rate(self):
        """Source should extract conciliation rate percentage."""
        from unittest.mock import MagicMock

        page = MagicMock()
        page.inner_text.return_value = (
            "Proveedor: AMAZON\nConciliación: 45.2%\nQuejas: 200 quejas\n"
        )

        src = ProfecoSource()
        result = src._parse_result(page, "AMAZON")

        assert result.conciliation_rate == "45.2%"
