"""Tests for 6 new Colombian sources (v0.5.0).

Tests _parse_result logic, meta(), supports(), and input validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# co.estado_cedula_extranjeria
# ===========================================================================


class TestEstadoCedulaExtranjeriaParseResult:
    def _parse(self, body_text: str, cedula: str = "E-123456"):
        from openquery.sources.co.estado_cedula_extranjeria import EstadoCedulaExtranjeriaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = EstadoCedulaExtranjeriaSource()
        return src._parse_result(page, cedula, "2020-01-15")

    def test_vigente(self):
        result = self._parse("Estado: VIGENTE\nNombre: Juan Carlos Lopez\nNacionalidad: VENEZUELA")
        assert result.estado == "Vigente"
        assert result.nombre == "Juan Carlos Lopez"
        assert result.nacionalidad == "VENEZUELA"

    def test_vencida(self):
        result = self._parse("Su cédula de extranjería se encuentra vencida desde 2023-01-01")
        assert result.estado == "Vencida"

    def test_cancelada(self):
        result = self._parse("La cédula ha sido cancelada por disposición administrativa")
        assert result.estado == "Cancelada"

    def test_no_registrada(self):
        result = self._parse("No se encontró información para el número consultado")
        assert result.estado == "No registrada"

    def test_cedula_preserved(self):
        result = self._parse("Estado: Vigente", cedula="E-999999")
        assert result.cedula_extranjeria == "E-999999"

    def test_verification_code(self):
        result = self._parse("Estado: Vigente\nCódigo verificación: ABC123XYZ")
        assert result.codigo_verificacion == "ABC123XYZ"


class TestEstadoCedulaExtranjeriaSource:
    def test_meta(self):
        from openquery.sources.co.estado_cedula_extranjeria import EstadoCedulaExtranjeriaSource

        meta = EstadoCedulaExtranjeriaSource().meta()
        assert meta.name == "co.estado_cedula_extranjeria"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True
        assert meta.country == "CO"

    def test_empty_cedula_raises(self):
        from openquery.sources.co.estado_cedula_extranjeria import EstadoCedulaExtranjeriaSource

        src = EstadoCedulaExtranjeriaSource()
        with pytest.raises(SourceError, match="required"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))

    def test_model_roundtrip(self):
        from openquery.models.co.estado_cedula_extranjeria import EstadoCedulaExtranjeriaResult

        r = EstadoCedulaExtranjeriaResult(
            cedula_extranjeria="E-123", estado="Vigente", mensaje="OK"
        )
        data = r.model_dump_json()
        r2 = EstadoCedulaExtranjeriaResult.model_validate_json(data)
        assert r2.estado == "Vigente"
        assert r2.cedula_extranjeria == "E-123"


# ===========================================================================
# co.validar_policia
# ===========================================================================


class TestValidarPoliciaParseResult:
    def _parse(
        self, body_text: str, cedula: str = "12345", placa: str = "P001", carnet: str = "C001"
    ):
        from openquery.sources.co.validar_policia import ValidarPoliciaSource

        page = MagicMock()
        page.inner_text.return_value = body_text
        src = ValidarPoliciaSource()
        return src._parse_result(page, cedula, placa, carnet)

    def test_active_officer(self):
        result = self._parse(
            "El funcionario es un funcionario activo de la Policía Nacional\nNombre: Pedro Gómez\nGrado: Patrullero"  # noqa: E501
        )
        assert result.es_policia_activo is True
        assert result.nombre == "Pedro Gómez"
        assert result.grado == "Patrullero"

    def test_not_found(self):
        result = self._parse("Los datos no coinciden con un funcionario activo")
        assert result.es_policia_activo is False

    def test_does_not_belong(self):
        result = self._parse("La persona no pertenece a la institución")
        assert result.es_policia_activo is False

    def test_fields_preserved(self):
        result = self._parse("No registra", cedula="99999", placa="P555", carnet="C777")
        assert result.cedula == "99999"
        assert result.placa == "P555"
        assert result.carnet == "C777"


class TestValidarPoliciaSource:
    def test_meta(self):
        from openquery.sources.co.validar_policia import ValidarPoliciaSource

        meta = ValidarPoliciaSource().meta()
        assert meta.name == "co.validar_policia"
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_missing_placa_and_carnet_raises(self):
        from openquery.sources.co.validar_policia import ValidarPoliciaSource

        src = ValidarPoliciaSource()
        with pytest.raises(SourceError, match="placa_policia"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number="12345"))

    def test_model_roundtrip(self):
        from openquery.models.co.validar_policia import ValidarPoliciaResult

        r = ValidarPoliciaResult(
            cedula="123", placa="P1", carnet="C1", es_policia_activo=True, mensaje="OK"
        )
        data = r.model_dump_json()
        r2 = ValidarPoliciaResult.model_validate_json(data)
        assert r2.es_policia_activo is True


# ===========================================================================
# co.rne
# ===========================================================================


class TestRneSource:
    def test_meta(self):
        from openquery.sources.co.rne import RneSource

        meta = RneSource().meta()
        assert meta.name == "co.rne"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False

    def test_missing_phone_and_email_raises(self):
        from openquery.sources.co.rne import RneSource

        src = RneSource()
        with pytest.raises(SourceError, match="telefono"):
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={"usuario": "u", "password": "p"},
                )
            )

    def test_missing_credentials_raises(self):
        from openquery.sources.co.rne import RneSource

        src = RneSource()
        with pytest.raises(SourceError, match="usuario"):
            src.query(
                QueryInput(
                    document_type=DocumentType.CUSTOM,
                    document_number="",
                    extra={"telefono": "3001234567"},
                )
            )

    def test_model_roundtrip(self):
        from openquery.models.co.rne import RneResult

        r = RneResult(
            consulta="3001234567", tipo_consulta="telefono", esta_excluido=True, mensaje="Excluido"
        )
        data = r.model_dump_json()
        r2 = RneResult.model_validate_json(data)
        assert r2.esta_excluido is True
        assert r2.tipo_consulta == "telefono"


# ===========================================================================
# co.camara_comercio_medellin
# ===========================================================================


class TestCamaraComercioMedellinParseResult:
    def _parse(self, body_text: str, rows_data=None, query="901234567"):
        from openquery.sources.co.camara_comercio_medellin import CamaraComercioMedellinSource

        page = MagicMock()
        page.inner_text.return_value = body_text

        if rows_data:
            mock_rows = []
            for row_values in rows_data:
                row = MagicMock()
                cells = []
                for val in row_values:
                    cell = MagicMock()
                    cell.inner_text.return_value = val
                    cells.append(cell)
                row.query_selector_all.return_value = cells
                mock_rows.append(row)
            page.query_selector_all.return_value = mock_rows
        else:
            page.query_selector_all.return_value = []

        src = CamaraComercioMedellinSource()
        return src._parse_result(page, query, "nit")

    def test_no_results(self):
        result = self._parse("No se encontraron resultados para su búsqueda")
        assert result.total_expedientes == 0
        assert "no se encontraron" in result.mensaje.lower()

    def test_table_results(self):
        rows = [
            ["12345", "ACME S.A.S.", "ACTIVA", "Persona Jurídica", "2020-01-15"],
            ["12346", "ACME SUCURSAL", "ACTIVA", "Establecimiento", "2020-06-01"],
        ]
        result = self._parse("Resultados de búsqueda", rows_data=rows)
        assert result.total_expedientes == 2
        assert result.expedientes[0].razon_social == "ACME S.A.S."
        assert result.expedientes[1].tipo == "Establecimiento"

    def test_model_roundtrip(self):
        from openquery.models.co.camara_comercio_medellin import CamaraComercioMedellinResult

        r = CamaraComercioMedellinResult(
            query="test", tipo_busqueda="nit", total_expedientes=0, mensaje="OK"
        )
        data = r.model_dump_json()
        r2 = CamaraComercioMedellinResult.model_validate_json(data)
        assert r2.query == "test"


class TestCamaraComercioMedellinSource:
    def test_meta(self):
        from openquery.sources.co.camara_comercio_medellin import CamaraComercioMedellinSource

        meta = CamaraComercioMedellinSource().meta()
        assert meta.name == "co.camara_comercio_medellin"
        assert DocumentType.NIT in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs

    def test_empty_query_raises(self):
        from openquery.sources.co.camara_comercio_medellin import CamaraComercioMedellinSource

        src = CamaraComercioMedellinSource()
        with pytest.raises(SourceError, match="NIT or company name"):
            src.query(QueryInput(document_type=DocumentType.NIT, document_number=""))


# ===========================================================================
# co.directorio_empresas
# ===========================================================================


class TestDirectorioEmpresasSource:
    def test_meta(self):
        from openquery.sources.co.directorio_empresas import DirectorioEmpresasSource

        meta = DirectorioEmpresasSource().meta()
        assert meta.name == "co.directorio_empresas"
        assert DocumentType.NIT in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False

    def test_empty_query_raises(self):
        from openquery.sources.co.directorio_empresas import DirectorioEmpresasSource

        src = DirectorioEmpresasSource()
        with pytest.raises(SourceError, match="NIT or company name"):
            src.query(QueryInput(document_type=DocumentType.NIT, document_number=""))

    def test_model_roundtrip(self):
        from openquery.models.co.directorio_empresas import (
            DirectorioEmpresasResult,
            EmpresaDirectorio,
        )

        emp = EmpresaDirectorio(razon_social="ACME", nit="900123456", municipio="MEDELLIN")
        r = DirectorioEmpresasResult(
            query="900123456", tipo_busqueda="nit", empresas=[emp], total_empresas=1, mensaje="OK"
        )
        data = r.model_dump_json()
        r2 = DirectorioEmpresasResult.model_validate_json(data)
        assert r2.total_empresas == 1
        assert r2.empresas[0].razon_social == "ACME"


# ===========================================================================
# co.empresas_google
# ===========================================================================


class TestEmpresasGoogleParseResult:
    def _parse(self, items_data=None, query="restaurantes"):
        from openquery.sources.co.empresas_google import EmpresasGoogleSource

        page = MagicMock()
        page.inner_text.return_value = "Google Maps results"

        if items_data:
            mock_items = []
            for text in items_data:
                item = MagicMock()
                item.inner_text.return_value = text
                mock_items.append(item)
            page.query_selector_all.return_value = mock_items
        else:
            page.query_selector_all.return_value = []

        src = EmpresasGoogleSource()
        return src._parse_result(page, query, "Medellín")

    def test_no_results(self):
        result = self._parse()
        assert result.total_empresas == 0
        assert "no se encontraron" in result.mensaje.lower()

    def test_parse_business_cards(self):
        cards = [
            "La Gran Parrilla\nRestaurante\n4.5(234)\nCalle 10 #43-12, El Poblado\n604 123 4567",
            "El Buen Sabor\nComida colombiana\n4.2(89)\nCarrera 70 #1-50",
        ]
        result = self._parse(items_data=cards)
        assert result.total_empresas == 2
        assert result.empresas[0].nombre == "La Gran Parrilla"
        assert result.empresas[0].rating == "4.5"
        assert result.empresas[0].total_resenas == "234"

    def test_model_roundtrip(self):
        from openquery.models.co.empresas_google import EmpresaGoogle, EmpresasGoogleResult

        emp = EmpresaGoogle(nombre="Test", rating="4.0", categoria="Restaurante")
        r = EmpresasGoogleResult(
            query="test", ubicacion="Colombia", empresas=[emp], total_empresas=1, mensaje="OK"
        )
        data = r.model_dump_json()
        r2 = EmpresasGoogleResult.model_validate_json(data)
        assert r2.empresas[0].nombre == "Test"


class TestEmpresasGoogleSource:
    def test_meta(self):
        from openquery.sources.co.empresas_google import EmpresasGoogleSource

        meta = EmpresasGoogleSource().meta()
        assert meta.name == "co.empresas_google"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.rate_limit_rpm == 5

    def test_empty_query_raises(self):
        from openquery.sources.co.empresas_google import EmpresasGoogleSource

        src = EmpresasGoogleSource()
        with pytest.raises(SourceError, match="query"):
            src.query(QueryInput(document_type=DocumentType.CUSTOM, document_number=""))


# ===========================================================================
# Registry integration — all 6 sources discoverable
# ===========================================================================


class TestNewSourcesRegistered:
    """Verify all 6 new sources appear in the registry."""

    @pytest.mark.parametrize(
        "source_name",
        [
            "co.estado_cedula_extranjeria",
            "co.validar_policia",
            "co.rne",
            "co.camara_comercio_medellin",
            "co.directorio_empresas",
            "co.empresas_google",
        ],
    )
    def test_source_registered(self, source_name):
        from openquery.sources import get_source

        src = get_source(source_name)
        assert src.meta().name == source_name
        assert src.meta().country == "CO"
