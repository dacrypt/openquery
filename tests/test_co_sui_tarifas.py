"""Tests for co.sui_tarifas — SUI electricity tariffs (live browser scraping)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput


class TestSuiTarifasResult:
    def test_defaults(self):
        from openquery.models.co.sui_tarifas import SuiTarifasResult

        r = SuiTarifasResult()
        assert r.ciudad == ""
        assert r.operador == ""
        assert r.estrato == ""
        assert r.total == 0
        assert r.tarifas == []
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.co.sui_tarifas import SuiTarifa, SuiTarifasResult

        r = SuiTarifasResult(
            ciudad="Bogota",
            operador="ENEL",
            estrato="3",
            total=1,
            tarifas=[
                SuiTarifa(
                    operador="ENEL",
                    estrato="3",
                    periodo="2024-01",
                    valor_kwh="850.50",
                )
            ],
        )
        dumped = r.model_dump_json()
        restored = SuiTarifasResult.model_validate_json(dumped)
        assert restored.ciudad == "Bogota"
        assert restored.operador == "ENEL"
        assert restored.total == 1
        assert len(restored.tarifas) == 1
        assert restored.tarifas[0].valor_kwh == "850.50"

    def test_audit_excluded_from_json(self):
        from openquery.models.co.sui_tarifas import SuiTarifasResult

        r = SuiTarifasResult(audit={"raw": "data"})
        assert "audit" not in r.model_dump()

    def test_sui_tarifa_defaults(self):
        from openquery.models.co.sui_tarifas import SuiTarifa

        t = SuiTarifa()
        assert t.operador == ""
        assert t.estrato == ""
        assert t.periodo == ""
        assert t.valor_kwh == ""
        assert t.componente_generacion == ""
        assert t.componente_transmision == ""
        assert t.componente_distribucion == ""
        assert t.componente_comercializacion == ""
        assert t.componente_perdidas == ""
        assert t.componente_restricciones == ""


class TestSuiTarifasSourceMeta:
    def test_meta_name(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        assert SuiTarifasSource().meta().name == "co.sui_tarifas"

    def test_meta_country(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        assert SuiTarifasSource().meta().country == "CO"

    def test_meta_supports_custom(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        assert DocumentType.CUSTOM in SuiTarifasSource().meta().supported_inputs

    def test_meta_requires_browser(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        assert SuiTarifasSource().meta().requires_browser is True

    def test_meta_rate_limit(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        assert SuiTarifasSource().meta().rate_limit_rpm == 5

    def test_meta_timeout_default(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        src = SuiTarifasSource()
        assert src._timeout == 60.0


class TestSuiTarifasParseResult:
    def _make_input(self, extra: dict | None = None) -> QueryInput:
        return QueryInput(
            document_number="search",
            document_type=DocumentType.CUSTOM,
            extra=extra or {"ciudad": "Bogota", "estrato": "3"},
        )

    def test_empty_input_raises(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        with pytest.raises(SourceError, match="co.sui_tarifas"):
            SuiTarifasSource().query(
                QueryInput(document_number="", document_type=DocumentType.CUSTOM)
            )

    def test_wrong_type_raises(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        with pytest.raises(SourceError, match="co.sui_tarifas"):
            SuiTarifasSource().query(
                QueryInput(document_number="12345", document_type=DocumentType.CEDULA)
            )

    def test_ciudad_resolves_to_operator(self):
        from openquery.sources.co.sui_tarifas import _CITY_TO_OPERATOR

        assert _CITY_TO_OPERATOR.get("bogota") == "ENEL"
        assert _CITY_TO_OPERATOR.get("medellin") == "EPM"
        assert _CITY_TO_OPERATOR.get("cali") == "EMCALI"

    def test_query_with_mocked_page_returns_result(self):
        from openquery.sources.co.sui_tarifas import SuiTarifasSource

        mock_page = MagicMock()
        mock_page.inner_text.return_value = (
            "Tarifa de Energía\n"
            "Operador: ENEL\n"
            "Estrato: 3\n"
            "Valor $/kWh: 850.50\n"
            "Generación: 250.00\n"
            "Transmisión: 50.00\n"
            "Distribución: 300.00\n"
            "Comercialización: 150.00\n"
            "Pérdidas: 80.50\n"
            "Restricciones: 20.00\n"
        )
        mock_page.query_selector_all.return_value = []
        mock_page.query_selector.return_value = None
        mock_page.wait_for_load_state = MagicMock()
        mock_page.wait_for_timeout = MagicMock()

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_page)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("openquery.core.browser.BrowserManager") as mock_bm:
            mock_bm.return_value.page.return_value = mock_ctx
            result = SuiTarifasSource().query(self._make_input())

        assert result.ciudad == "Bogota"
        assert result.operador == "ENEL"
        assert result.estrato == "3"

    def test_map_columns_operator(self):
        from openquery.sources.co.sui_tarifas import _map_columns

        headers = ["operador", "estrato", "periodo", "cu total", "generación"]
        col_map = _map_columns(headers)
        assert col_map["operador"] == 0
        assert col_map["estrato"] == 1
        assert col_map["periodo"] == 2
        assert col_map["valor_kwh"] == 3
        assert col_map["componente_generacion"] == 4

    def test_map_columns_empresa(self):
        from openquery.sources.co.sui_tarifas import _map_columns

        headers = ["empresa prestador", "nivel", "mes"]
        col_map = _map_columns(headers)
        assert col_map["operador"] == 0
        assert col_map["estrato"] == 1
        assert col_map["periodo"] == 2
