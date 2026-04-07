"""Unit tests for Colombian departmental vehicle tax sources."""

from __future__ import annotations

from unittest.mock import MagicMock

from openquery.models.co.impuesto_vehicular import ImpuestoVehicularResult, VigenciaPendiente
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource
from openquery.sources.co.impuesto_vehicular_antioquia import ImpuestoVehicularAntioquiaSource
from openquery.sources.co.impuesto_vehicular_atlantico import ImpuestoVehicularAtlanticoSource
from openquery.sources.co.impuesto_vehicular_bogota import ImpuestoVehicularBogotaSource
from openquery.sources.co.impuesto_vehicular_bolivar import ImpuestoVehicularBolivarSource
from openquery.sources.co.impuesto_vehicular_boyaca import ImpuestoVehicularBoyacaSource
from openquery.sources.co.impuesto_vehicular_caldas import ImpuestoVehicularCaldasSource
from openquery.sources.co.impuesto_vehicular_cundinamarca import ImpuestoVehicularCundinamarcaSource
from openquery.sources.co.impuesto_vehicular_huila import ImpuestoVehicularHuilaSource
from openquery.sources.co.impuesto_vehicular_meta import ImpuestoVehicularMetaSource
from openquery.sources.co.impuesto_vehicular_narino import ImpuestoVehicularNarinoSource
from openquery.sources.co.impuesto_vehicular_norte_santander import (
    ImpuestoVehicularNorteSantanderSource,
)
from openquery.sources.co.impuesto_vehicular_risaralda import ImpuestoVehicularRisaraldaSource
from openquery.sources.co.impuesto_vehicular_santander import ImpuestoVehicularSantanderSource
from openquery.sources.co.impuesto_vehicular_tolima import ImpuestoVehicularTolimaSource
from openquery.sources.co.impuesto_vehicular_valle import ImpuestoVehicularValleSource

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestVigenciaPendiente:
    """Test VigenciaPendiente nested model."""

    def test_default_values(self):
        v = VigenciaPendiente()
        assert v.year == ""
        assert v.value == ""
        assert v.status == ""

    def test_with_data(self):
        v = VigenciaPendiente(year="2023", value="1.500.000", status="Pendiente")
        assert v.year == "2023"
        assert v.value == "1.500.000"
        assert v.status == "Pendiente"

    def test_round_trip_json(self):
        v = VigenciaPendiente(year="2022", value="800.000", status="Vencida")
        restored = VigenciaPendiente.model_validate_json(v.model_dump_json())
        assert restored.year == "2022"
        assert restored.value == "800.000"
        assert restored.status == "Vencida"


class TestImpuestoVehicularResult:
    """Test ImpuestoVehicularResult model."""

    def test_default_values(self):
        r = ImpuestoVehicularResult()
        assert r.placa == ""
        assert r.departamento == ""
        assert r.marca == ""
        assert r.modelo == ""
        assert r.cilindraje == ""
        assert r.tipo_servicio == ""
        assert r.avaluo == ""
        assert r.total_deuda == ""
        assert r.vigencias_pendientes == []
        assert r.estado == ""
        assert r.details == {}
        assert r.audit is None

    def test_audit_excluded_from_json(self):
        r = ImpuestoVehicularResult(placa="ABC123")
        r.audit = object()
        dumped = r.model_dump_json()
        assert "audit" not in dumped

    def test_round_trip_json(self):
        vigencias = [VigenciaPendiente(year="2023", value="1.200.000", status="Pendiente")]
        r = ImpuestoVehicularResult(
            placa="XYZ789",
            departamento="Bogotá D.C.",
            marca="CHEVROLET",
            modelo="2018",
            cilindraje="1600",
            tipo_servicio="PARTICULAR",
            avaluo="45.000.000",
            total_deuda="1.200.000",
            vigencias_pendientes=vigencias,
            estado="CON DEUDA",
            details={"Clase": "AUTOMOVIL"},
        )
        restored = ImpuestoVehicularResult.model_validate_json(r.model_dump_json())
        assert restored.placa == "XYZ789"
        assert restored.departamento == "Bogotá D.C."
        assert restored.marca == "CHEVROLET"
        assert len(restored.vigencias_pendientes) == 1
        assert restored.vigencias_pendientes[0].year == "2023"
        assert restored.details["Clase"] == "AUTOMOVIL"

    def test_paz_y_salvo(self):
        r = ImpuestoVehicularResult(placa="ABC123", estado="PAZ Y SALVO", total_deuda="0")
        assert r.estado == "PAZ Y SALVO"
        assert r.total_deuda == "0"

    def test_multiple_vigencias(self):
        vigencias = [
            VigenciaPendiente(year="2021", value="900.000"),
            VigenciaPendiente(year="2022", value="1.000.000"),
            VigenciaPendiente(year="2023", value="1.100.000"),
        ]
        r = ImpuestoVehicularResult(vigencias_pendientes=vigencias)
        assert len(r.vigencias_pendientes) == 3
        assert r.vigencias_pendientes[0].year == "2021"


# ---------------------------------------------------------------------------
# Source meta tests
# ---------------------------------------------------------------------------

ALL_SOURCES = [
    (ImpuestoVehicularBogotaSource, "co.impuesto_vehicular_bogota", "Bogotá D.C.", False),
    (ImpuestoVehicularAntioquiaSource, "co.impuesto_vehicular_antioquia", "Antioquia", True),
    (ImpuestoVehicularValleSource, "co.impuesto_vehicular_valle", "Valle del Cauca", True),
    (ImpuestoVehicularCundinamarcaSource, "co.impuesto_vehicular_cundinamarca", "Cundinamarca", False),  # noqa: E501
    (ImpuestoVehicularAtlanticoSource, "co.impuesto_vehicular_atlantico", "Atlántico", False),
    (ImpuestoVehicularSantanderSource, "co.impuesto_vehicular_santander", "Santander", False),
    (ImpuestoVehicularBolivarSource, "co.impuesto_vehicular_bolivar", "Bolívar", False),
    (ImpuestoVehicularNorteSantanderSource, "co.impuesto_vehicular_norte_santander", "Norte de Santander", False),  # noqa: E501
    (ImpuestoVehicularBoyacaSource, "co.impuesto_vehicular_boyaca", "Boyacá", False),
    (ImpuestoVehicularNarinoSource, "co.impuesto_vehicular_narino", "Nariño", False),
    (ImpuestoVehicularRisaraldaSource, "co.impuesto_vehicular_risaralda", "Risaralda", True),
    (ImpuestoVehicularCaldasSource, "co.impuesto_vehicular_caldas", "Caldas", False),
    (ImpuestoVehicularTolimaSource, "co.impuesto_vehicular_tolima", "Tolima", True),
    (ImpuestoVehicularHuilaSource, "co.impuesto_vehicular_huila", "Huila", True),
    (ImpuestoVehicularMetaSource, "co.impuesto_vehicular_meta", "Meta", True),
]


class TestAllSourceMeta:
    """Test meta() for all 15 sources."""

    def test_source_count(self):
        assert len(ALL_SOURCES) == 15

    def test_bogota_meta(self):
        src = ImpuestoVehicularBogotaSource()
        meta = src.meta()
        assert meta.name == "co.impuesto_vehicular_bogota"
        assert meta.country == "CO"
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 5
        assert meta.requires_captcha is False
        from openquery.sources.base import DocumentType
        assert DocumentType.PLATE in meta.supported_inputs

    def test_atlantico_requires_captcha(self):
        src = ImpuestoVehicularAtlanticoSource()
        meta = src.meta()
        assert meta.requires_captcha is True

    def test_all_meta_fields(self):
        from openquery.sources.base import DocumentType
        for cls, expected_name, expected_dept, expected_needs_doc in ALL_SOURCES:
            src = cls()
            meta = src.meta()
            assert meta.name == expected_name, f"{cls.__name__}: wrong name"
            assert meta.country == "CO", f"{cls.__name__}: wrong country"
            assert meta.requires_browser is True, f"{cls.__name__}: requires_browser should be True"
            assert meta.rate_limit_rpm == 5, f"{cls.__name__}: rate_limit_rpm should be 5"
            assert DocumentType.PLATE in meta.supported_inputs, (
                f"{cls.__name__}: PLATE not in supported_inputs"
            )
            assert src._departamento == expected_dept, f"{cls.__name__}: wrong departamento"
            assert src._needs_documento == expected_needs_doc, (
                f"{cls.__name__}: wrong _needs_documento"
            )

    def test_all_source_names_unique(self):
        names = [cls().meta().name for cls, *_ in ALL_SOURCES]
        assert len(names) == len(set(names)), "Duplicate source names found"

    def test_all_sources_have_url(self):
        for cls, *_ in ALL_SOURCES:
            src = cls()
            meta = src.meta()
            assert meta.url.startswith("https://"), f"{cls.__name__}: URL should start with https://"

    def test_default_timeout(self):
        for cls, *_ in ALL_SOURCES:
            src = cls()
            assert src._timeout == 45.0, f"{cls.__name__}: default timeout should be 45.0"


# ---------------------------------------------------------------------------
# _parse_result tests (unit, no browser)
# ---------------------------------------------------------------------------

def _make_mock_page(body_text: str, rows: list[list[str]] | None = None) -> MagicMock:
    """Build a mock page that returns body_text and optional table rows."""
    page = MagicMock()
    page.inner_text.return_value = body_text

    mock_rows = []
    for row_cells in (rows or []):
        cells = []
        for cell_text in row_cells:
            cell = MagicMock()
            cell.inner_text.return_value = cell_text
            cells.append(cell)
        mock_row = MagicMock()
        mock_row.query_selector_all.return_value = cells
        mock_rows.append(mock_row)

    page.query_selector_all.return_value = mock_rows
    return page


class TestParseResult:
    """Test _parse_result via ImpuestoVehicularBaseSource (using Bogotá as a concrete subclass)."""

    def _source(self):
        return ImpuestoVehicularBogotaSource()

    def test_parse_paz_y_salvo(self):
        src = self._source()
        page = _make_mock_page("Vehículo en Paz y Salvo. No tiene deudas pendientes.")
        result = src._parse_result(page, "ABC123")
        assert result.placa == "ABC123"
        assert result.departamento == "Bogotá D.C."
        assert result.estado == "PAZ Y SALVO"

    def test_parse_con_deuda(self):
        src = self._source()
        body = "Total deuda: $ 2.500.000\nMarca: RENAULT\nModelo: 2019\nCilindraje: 1400"
        page = _make_mock_page(body)
        result = src._parse_result(page, "XYZ789")
        assert result.total_deuda == "2.500.000"
        assert result.marca == "RENAULT"
        assert result.modelo == "2019"
        assert result.cilindraje == "1400"
        assert result.estado == "CON DEUDA"

    def test_parse_vigencias_from_table(self):
        src = self._source()
        body = "Vigencias pendientes"
        rows = [
            ["2021", "900.000", "Pendiente"],
            ["2022", "1.000.000", "Pendiente"],
            ["2023", "1.100.000", "Vencida"],
        ]
        page = _make_mock_page(body, rows)
        result = src._parse_result(page, "DEF456")
        assert len(result.vigencias_pendientes) == 3
        assert result.vigencias_pendientes[0].year == "2021"
        assert result.vigencias_pendientes[0].value == "900.000"
        assert result.vigencias_pendientes[0].status == "Pendiente"
        assert result.vigencias_pendientes[2].year == "2023"
        assert result.vigencias_pendientes[2].status == "Vencida"

    def test_parse_empty_page(self):
        src = self._source()
        page = _make_mock_page("")
        result = src._parse_result(page, "GHI789")
        assert result.placa == "GHI789"
        assert result.marca == ""
        assert result.total_deuda == ""
        assert result.estado == ""
        assert result.vigencias_pendientes == []

    def test_parse_avaluo(self):
        src = self._source()
        body = "Avalúo: $ 38.000.000\nServicio: PARTICULAR"
        page = _make_mock_page(body)
        result = src._parse_result(page, "JKL012")
        assert result.avaluo == "38.000.000"
        assert result.tipo_servicio == "PARTICULAR"

    def test_parse_non_year_table_rows_go_to_details(self):
        src = self._source()
        body = ""
        rows = [
            ["Clase", "AUTOMOVIL"],
            ["Color", "BLANCO"],
            ["2023", "500.000"],
        ]
        page = _make_mock_page(body, rows)
        result = src._parse_result(page, "MNO345")
        assert result.details.get("Clase") == "AUTOMOVIL"
        assert result.details.get("Color") == "BLANCO"
        assert len(result.vigencias_pendientes) == 1
        assert result.vigencias_pendientes[0].year == "2023"


class TestParseResultAntioquia:
    """Test _parse_result for Antioquia source (needs_documento=True)."""

    def test_parse_basic(self):
        src = ImpuestoVehicularAntioquiaSource()
        body = "Total: $ 3.200.000\nMarca: CHEVROLET\nModelo: 2020"
        page = _make_mock_page(body)
        result = src._parse_result(page, "PQR678")
        assert result.departamento == "Antioquia"
        assert result.total_deuda == "3.200.000"
        assert result.marca == "CHEVROLET"


class TestSourceInit:
    """Test source initialization."""

    def test_default_init(self):
        src = ImpuestoVehicularBogotaSource()
        assert src._timeout == 45.0
        assert src._headless is True

    def test_custom_timeout(self):
        src = ImpuestoVehicularBogotaSource(timeout=60.0)
        assert src._timeout == 60.0

    def test_custom_headless(self):
        src = ImpuestoVehicularBogotaSource(headless=False)
        assert src._headless is False

    def test_is_base_source(self):
        src = ImpuestoVehicularBogotaSource()
        assert isinstance(src, ImpuestoVehicularBaseSource)
