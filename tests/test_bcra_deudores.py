"""Unit tests for Argentina BCRA Central de Deudores source."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openquery.models.ar.bcra_deudores import BcraDebt, BcraDeudoresResult
from openquery.sources.ar.bcra_deudores import BcraDeudoresSource


class TestBcraDeudoresResult:
    """Test BcraDeudoresResult model."""

    def test_default_values(self):
        data = BcraDeudoresResult()
        assert data.identificacion == ""
        assert data.denominacion == ""
        assert data.total_debts == 0
        assert data.debts == []
        assert data.periods_checked == 0
        assert data.worst_situation == 0
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = BcraDeudoresResult(
            identificacion="20123456789",
            denominacion="ACME SA",
            total_debts=2,
            debts=[
                BcraDebt(entity="Banco Nacion", situation=1, amount=50000.0, period="202401"),
                BcraDebt(entity="Banco Patagonia", situation=2, amount=10000.0, period="202402"),
            ],
            periods_checked=3,
            worst_situation=2,
        )
        json_str = data.model_dump_json()
        restored = BcraDeudoresResult.model_validate_json(json_str)
        assert restored.identificacion == "20123456789"
        assert restored.denominacion == "ACME SA"
        assert restored.total_debts == 2
        assert len(restored.debts) == 2
        assert restored.debts[0].entity == "Banco Nacion"
        assert restored.worst_situation == 2

    def test_audit_excluded_from_json(self):
        data = BcraDeudoresResult(identificacion="20123456789", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}

    def test_bcra_debt_default_values(self):
        debt = BcraDebt()
        assert debt.entity == ""
        assert debt.situation == 0
        assert debt.amount == 0.0
        assert debt.period == ""


class TestBcraDeudoresSourceMeta:
    """Test BcraDeudoresSource metadata."""

    def test_meta_name(self):
        source = BcraDeudoresSource()
        assert source.meta().name == "ar.bcra_deudores"

    def test_meta_country(self):
        source = BcraDeudoresSource()
        assert source.meta().country == "AR"

    def test_meta_requires_browser(self):
        source = BcraDeudoresSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = BcraDeudoresSource()
        assert source.meta().requires_captcha is False

    def test_meta_rate_limit(self):
        source = BcraDeudoresSource()
        assert source.meta().rate_limit_rpm == 20

    def test_default_timeout(self):
        source = BcraDeudoresSource()
        assert source._timeout == 15.0

    def test_custom_timeout(self):
        source = BcraDeudoresSource(timeout=30.0)
        assert source._timeout == 30.0

    def test_meta_supported_inputs(self):
        from openquery.sources.base import DocumentType

        source = BcraDeudoresSource()
        assert DocumentType.CUSTOM in source.meta().supported_inputs


class TestParseResult:
    """Test _parse_response parsing logic."""

    def test_parse_with_debts(self):
        source = BcraDeudoresSource()
        data = {
            "results": {
                "denominacion": "EMPRESA SA",
                "periodos": [
                    {
                        "periodo": "202401",
                        "entidades": [
                            {"entidad": "Banco Nacion", "situacion": 1, "monto": 100000},
                            {"entidad": "Banco Patagonia", "situacion": 3, "monto": 5000},
                        ],
                    },
                    {
                        "periodo": "202402",
                        "entidades": [
                            {"entidad": "Banco Nacion", "situacion": 1, "monto": 95000},
                        ],
                    },
                ],
            }
        }
        result = source._parse_response("20123456789", data)
        assert result.identificacion == "20123456789"
        assert result.denominacion == "EMPRESA SA"
        assert result.total_debts == 3
        assert result.periods_checked == 2
        assert result.worst_situation == 3
        assert len(result.debts) == 3
        assert result.debts[0].entity == "Banco Nacion"
        assert result.debts[0].situation == 1
        assert result.debts[0].amount == 100000.0
        assert result.debts[0].period == "202401"

    def test_parse_empty_response(self):
        source = BcraDeudoresSource()
        data = {"results": {"denominacion": "SIN DEUDAS", "periodos": []}}
        result = source._parse_response("20111111111", data)
        assert result.total_debts == 0
        assert result.periods_checked == 0
        assert result.worst_situation == 0
        assert result.debts == []

    def test_parse_worst_situation_tracked(self):
        source = BcraDeudoresSource()
        data = {
            "results": {
                "denominacion": "TEST SA",
                "periodos": [
                    {
                        "periodo": "202401",
                        "entidades": [
                            {"entidad": "Banco A", "situacion": 2, "monto": 1000},
                            {"entidad": "Banco B", "situacion": 5, "monto": 2000},
                            {"entidad": "Banco C", "situacion": 1, "monto": 3000},
                        ],
                    }
                ],
            }
        }
        result = source._parse_response("20999999999", data)
        assert result.worst_situation == 5

    def test_query_strips_dashes(self):
        """CUIT with dashes is normalized before querying."""
        source = BcraDeudoresSource()
        api_response = {
            "results": {"denominacion": "TEST", "periodos": []},
        }
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = api_response
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
            result = source._query("20123456789")
        assert result.identificacion == "20123456789"
