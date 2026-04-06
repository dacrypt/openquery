"""Unit tests for Argentina SISA REFES source — health facility registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openquery.models.ar.sisa_refes import SisaRefesResult
from openquery.sources.ar.sisa_refes import SisaRefesSource


class TestSisaRefesResult:
    """Test SisaRefesResult model."""

    def test_default_values(self):
        data = SisaRefesResult()
        assert data.search_term == ""
        assert data.facility_name == ""
        assert data.facility_type == ""
        assert data.cuit == ""
        assert data.address == ""
        assert data.province == ""
        assert data.sector == ""
        assert data.services == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = SisaRefesResult(
            search_term="Hospital Central",
            facility_name="HOSPITAL CENTRAL DE MENDOZA",
            facility_type="Hospital General",
            cuit="30123456789",
            address="Av. Libertad 1234, Mendoza",
            province="Mendoza",
            sector="Público",
            services=["Urgencias", "Pediatría"],
        )
        json_str = data.model_dump_json()
        restored = SisaRefesResult.model_validate_json(json_str)
        assert restored.facility_name == "HOSPITAL CENTRAL DE MENDOZA"
        assert restored.cuit == "30123456789"
        assert restored.services == ["Urgencias", "Pediatría"]

    def test_audit_excluded_from_json(self):
        data = SisaRefesResult(search_term="test", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestSisaRefesSourceMeta:
    """Test SisaRefesSource metadata."""

    def test_meta_name(self):
        source = SisaRefesSource()
        assert source.meta().name == "ar.sisa_refes"

    def test_meta_country(self):
        source = SisaRefesSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = SisaRefesSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = SisaRefesSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = SisaRefesSource()
        assert source.meta().rate_limit_rpm == 10

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = SisaRefesSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs

    def test_default_timeout(self):
        source = SisaRefesSource()
        assert source._timeout == 20.0

    def test_custom_timeout(self):
        source = SisaRefesSource(timeout=30.0)
        assert source._timeout == 30.0


class TestParseResult:
    """Test _parse_response parsing logic."""

    def test_parse_establecimientos_list(self):
        source = SisaRefesSource()
        data = {
            "establecimientos": [
                {
                    "nombre": "HOSPITAL GENERAL DE AGUDOS",
                    "tipoEstablecimiento": "Hospital General",
                    "cuit": "30987654321",
                    "provincia": {"nombre": "Buenos Aires"},
                    "sector": "Público",
                    "domicilio": {"calle": "Av. Rivadavia", "numero": "2000", "localidad": "CABA"},
                    "servicios": [
                        {"nombre": "Urgencias"},
                        {"nombre": "Cirugía"},
                    ],
                    "cuie": "A12345",
                }
            ]
        }
        result = source._parse_response("Hospital General", data)
        assert result.facility_name == "HOSPITAL GENERAL DE AGUDOS"
        assert result.facility_type == "Hospital General"
        assert result.cuit == "30987654321"
        assert result.province == "Buenos Aires"
        assert result.sector == "Público"
        assert "Urgencias" in result.services
        assert "Cirugía" in result.services
        assert "Av. Rivadavia" in result.address
        assert result.details.get("cuie") == "A12345"

    def test_parse_direct_record(self):
        source = SisaRefesSource()
        data = {
            "nombre": "CLINICA SAN JOSE",
            "tipo": "Clínica",
            "cuit": "30111222333",
            "provincia": "Córdoba",
            "sector": "Privado",
            "domicilio": "Bv. San Juan 500",
            "servicios": ["Cardiología"],
        }
        result = source._parse_response("CLINICA SAN JOSE", data)
        assert result.facility_name == "CLINICA SAN JOSE"
        assert result.facility_type == "Clínica"
        assert result.cuit == "30111222333"
        assert result.province == "Córdoba"
        assert result.address == "Bv. San Juan 500"

    def test_parse_empty_response(self):
        source = SisaRefesSource()
        result = source._parse_response("nonexistent", {})
        assert result.facility_name == ""
        assert result.services == []

    def test_parse_services_as_strings(self):
        source = SisaRefesSource()
        data = {
            "establecimientos": [
                {
                    "nombre": "TEST",
                    "servicios": ["Pediatría", "Neurología"],
                }
            ]
        }
        result = source._parse_response("TEST", data)
        assert result.services == ["Pediatría", "Neurología"]

    def test_query_uses_code_param(self):
        source = SisaRefesSource()
        api_response = {"establecimientos": [{"nombre": "HOSPITAL X", "cuit": "30000000001"}]}
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = api_response
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
            result = source._query("A99999", code="A99999")
        assert result.facility_name == "HOSPITAL X"
